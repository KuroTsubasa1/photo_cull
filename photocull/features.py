"""Feature extraction for photo quality assessment"""

import cv2
import numpy as np
import mediapipe as mp
from PIL import Image
import imagehash
from typing import Optional, List, Tuple
from dataclasses import dataclass, field


@dataclass
class ImageMetrics:
    """Container for all extracted image metrics"""
    path: str
    phash: str = ""
    dhash: str = ""
    ahash: str = ""
    sharpness: float = 0.0
    sharpness_z: float = 0.0
    exposure_ok: float = 1.0
    eyes_open: float = 1.0
    face_count: int = 0
    face_regions: List[Tuple[int, int, int, int]] = field(default_factory=list)
    score: float = 0.0
    embedding: Optional[np.ndarray] = None
    width: int = 0
    height: int = 0
    filesize: int = 0
    
    def to_dict(self):
        d = vars(self).copy()
        if self.embedding is not None:
            d['embedding'] = self.embedding.tolist()
        return d


class FeatureExtractor:
    """Extract quality metrics from images"""
    
    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=10,
            min_detection_confidence=0.5
        )
        
    def extract_hashes(self, img_pil: Image.Image) -> Tuple[str, str, str]:
        """Extract perceptual hashes from image"""
        phash = str(imagehash.phash(img_pil))
        dhash = str(imagehash.dhash(img_pil))
        ahash = str(imagehash.average_hash(img_pil))
        return phash, dhash, ahash
    
    def compute_sharpness(self, img_cv: np.ndarray) -> float:
        """Compute variance of Laplacian (higher = sharper)"""
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY) if len(img_cv.shape) == 3 else img_cv
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return laplacian.var()
    
    def compute_exposure(self, img_cv: np.ndarray) -> float:
        """Compute exposure quality (1.0 = good, lower = clipped)"""
        if len(img_cv.shape) == 3:
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_cv
        
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        total_pixels = gray.shape[0] * gray.shape[1]
        
        # Check for clipping at dark and bright ends
        dark_clipped = hist[:5].sum() / total_pixels
        bright_clipped = hist[-5:].sum() / total_pixels
        
        # Penalize heavy clipping
        clipped_fraction = dark_clipped + bright_clipped
        return max(0.0, 1.0 - clipped_fraction)
    
    def compute_ear(self, landmarks: np.ndarray, eye_indices: List[int]) -> float:
        """Compute Eye Aspect Ratio for given eye landmarks"""
        # Vertical distances
        v1 = np.linalg.norm(landmarks[eye_indices[1]] - landmarks[eye_indices[5]])
        v2 = np.linalg.norm(landmarks[eye_indices[2]] - landmarks[eye_indices[4]])
        
        # Horizontal distance
        h = np.linalg.norm(landmarks[eye_indices[0]] - landmarks[eye_indices[3]])
        
        if h == 0:
            return 0.0
        
        ear = (v1 + v2) / (2.0 * h)
        return ear
    
    def detect_eyes_open(self, img_cv: np.ndarray) -> Tuple[float, int, List[Tuple[int, int, int, int]]]:
        """Detect faces and compute eyes-open percentage"""
        # Convert BGR to RGB for MediaPipe
        img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(img_rgb)
        
        if not results.multi_face_landmarks:
            return 1.0, 0, []
        
        h, w = img_cv.shape[:2]
        face_regions = []
        ears = []
        
        # MediaPipe eye landmark indices
        LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
        RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
        
        for face_landmarks in results.multi_face_landmarks:
            # Convert normalized landmarks to pixel coordinates
            landmarks = np.array([[lm.x * w, lm.y * h] for lm in face_landmarks.landmark])
            
            # Compute bounding box for face
            x_coords = landmarks[:, 0]
            y_coords = landmarks[:, 1]
            x_min, x_max = int(x_coords.min()), int(x_coords.max())
            y_min, y_max = int(y_coords.min()), int(y_coords.max())
            face_regions.append((x_min, y_min, x_max, y_max))
            
            # Compute EAR for both eyes
            left_ear = self.compute_ear(landmarks, LEFT_EYE_INDICES)
            right_ear = self.compute_ear(landmarks, RIGHT_EYE_INDICES)
            
            # Average EAR for this face
            avg_ear = (left_ear + right_ear) / 2.0
            ears.append(avg_ear)
        
        if ears:
            # Convert EARs to "eyes open" score (EAR > 0.22 typically means open)
            eyes_open_scores = [1.0 if ear > 0.22 else 0.0 for ear in ears]
            eyes_open_pct = sum(eyes_open_scores) / len(eyes_open_scores)
        else:
            eyes_open_pct = 1.0
        
        return eyes_open_pct, len(face_regions), face_regions
    
    def extract_all_features(self, img_path: str) -> ImageMetrics:
        """Extract all features from an image"""
        import os
        
        metrics = ImageMetrics(path=img_path)
        
        try:
            # Load image
            img_pil = Image.open(img_path).convert('RGB')
            img_cv = cv2.imread(img_path)
            
            if img_cv is None:
                return metrics
            
            metrics.width = img_pil.width
            metrics.height = img_pil.height
            metrics.filesize = os.path.getsize(img_path)
            
            # Extract hashes
            metrics.phash, metrics.dhash, metrics.ahash = self.extract_hashes(img_pil)
            
            # Compute quality metrics
            metrics.sharpness = self.compute_sharpness(img_cv)
            metrics.exposure_ok = self.compute_exposure(img_cv)
            
            # Detect faces and eyes
            metrics.eyes_open, metrics.face_count, metrics.face_regions = self.detect_eyes_open(img_cv)
            
        except Exception as e:
            print(f"[extract] Error processing {img_path}: {e}")
        
        return metrics


def extract_clip_embedding(img_path: str, model=None, processor=None) -> Optional[np.ndarray]:
    """Extract CLIP embedding for semantic similarity (optional)"""
    try:
        if model is None:
            import open_clip
            model, _, processor = open_clip.create_model_and_transforms('ViT-B-32', pretrained='openai')
            model.eval()
        
        from PIL import Image
        import torch
        
        image = processor(Image.open(img_path)).unsqueeze(0)
        with torch.no_grad():
            image_features = model.encode_image(image)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        
        return image_features.cpu().numpy().flatten()
    
    except ImportError:
        print("[clip] open_clip not installed, skipping embeddings")
        return None
    except Exception as e:
        print(f"[clip] Error extracting embedding: {e}")
        return None