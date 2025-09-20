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
    # Blur detection metrics
    is_blurry: bool = False
    blur_score: float = 0.0  # 0-1, higher = less blurry
    face_blur_scores: List[float] = field(default_factory=list)
    has_motion_blur: bool = False
    tenengrad_score: float = 0.0
    # Thumbnail path for UI display
    thumbnail_path: str = ""
    
    def to_dict(self):
        import numpy as np
        d = {}
        for key, value in vars(self).items():
            if isinstance(value, np.ndarray):
                d[key] = value.tolist()
            elif isinstance(value, (np.float32, np.float64)):
                d[key] = float(value)
            elif isinstance(value, (np.int32, np.int64)):
                d[key] = int(value)
            else:
                d[key] = value
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
    
    def compute_tenengrad(self, img_cv: np.ndarray) -> float:
        """Compute Tenengrad focus measure using Sobel operators"""
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY) if len(img_cv.shape) == 3 else img_cv
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(gx**2 + gy**2)
        return gradient_magnitude.mean()
    
    def detect_motion_blur(self, img_cv: np.ndarray) -> bool:
        """Detect motion blur using gradient energy ratio"""
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY) if len(img_cv.shape) == 3 else img_cv
        
        # Compute gradients in multiple directions
        kernels = {
            'horizontal': np.array([[1, 1, 1], [0, 0, 0], [-1, -1, -1]]),
            'vertical': np.array([[1, 0, -1], [1, 0, -1], [1, 0, -1]]),
            'diagonal1': np.array([[1, 1, 0], [1, 0, -1], [0, -1, -1]]),
            'diagonal2': np.array([[0, 1, 1], [-1, 0, 1], [-1, -1, 0]])
        }
        
        energies = []
        for kernel in kernels.values():
            filtered = cv2.filter2D(gray, cv2.CV_64F, kernel)
            energy = np.sum(filtered ** 2)
            energies.append(energy)
        
        # High variance in directional energies suggests motion blur
        energy_variance = np.var(energies) / (np.mean(energies) + 1e-10)
        return energy_variance > 0.5  # Threshold for motion blur detection
    
    def compute_blur_score(self, sharpness: float, img_shape: tuple) -> float:
        """Convert sharpness to normalized blur score (0-1, higher = less blurry)
        
        Args:
            sharpness: Variance of Laplacian
            img_shape: Image dimensions (height, width)
        
        Returns:
            Blur score from 0 (very blurry) to 1 (sharp)
        """
        # Adaptive threshold based on image size
        # Larger images tend to have higher variance
        pixel_count = img_shape[0] * img_shape[1]
        size_factor = np.log10(pixel_count / 1e6 + 1)  # Normalize for megapixels
        
        # Typical thresholds for different image sizes
        blur_threshold = 100 * (1 + size_factor)  # Very blurry
        sharp_threshold = 500 * (1 + size_factor)  # Sharp
        
        if sharpness < blur_threshold:
            return 0.0
        elif sharpness > sharp_threshold:
            return 1.0
        else:
            # Linear interpolation between thresholds
            return (sharpness - blur_threshold) / (sharp_threshold - blur_threshold)
    
    def compute_face_blur(self, img_cv: np.ndarray, face_regions: List[Tuple[int, int, int, int]]) -> List[float]:
        """Compute blur scores for face regions
        
        Returns:
            List of blur scores (0-1) for each face, higher = less blurry
        """
        face_blur_scores = []
        
        for (x_min, y_min, x_max, y_max) in face_regions:
            # Extract face region with padding
            padding = 10
            x_min = max(0, x_min - padding)
            y_min = max(0, y_min - padding)
            x_max = min(img_cv.shape[1], x_max + padding)
            y_max = min(img_cv.shape[0], y_max + padding)
            
            face_crop = img_cv[y_min:y_max, x_min:x_max]
            
            if face_crop.size == 0:
                face_blur_scores.append(0.0)
                continue
            
            # Compute sharpness for face region
            face_sharpness = self.compute_sharpness(face_crop)
            
            # More strict thresholds for faces
            blur_threshold = 50
            sharp_threshold = 200
            
            if face_sharpness < blur_threshold:
                score = 0.0
            elif face_sharpness > sharp_threshold:
                score = 1.0
            else:
                score = (face_sharpness - blur_threshold) / (sharp_threshold - blur_threshold)
            
            face_blur_scores.append(score)
        
        return face_blur_scores
    
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
        from .raw_utils import load_image_universal
        
        metrics = ImageMetrics(path=img_path)
        
        try:
            # Load image (handles both standard and raw formats)
            img_cv, img_pil = load_image_universal(img_path)
            
            if img_cv is None or img_pil is None:
                return metrics
            
            metrics.width = img_pil.width
            metrics.height = img_pil.height
            metrics.filesize = os.path.getsize(img_path)
            
            # Extract hashes
            metrics.phash, metrics.dhash, metrics.ahash = self.extract_hashes(img_pil)
            
            # Compute quality metrics
            metrics.sharpness = self.compute_sharpness(img_cv)
            metrics.exposure_ok = self.compute_exposure(img_cv)
            
            # Compute blur metrics
            metrics.blur_score = self.compute_blur_score(metrics.sharpness, img_cv.shape[:2])
            metrics.is_blurry = metrics.blur_score < 0.3  # Consider image blurry if score < 0.3
            metrics.tenengrad_score = self.compute_tenengrad(img_cv)
            metrics.has_motion_blur = self.detect_motion_blur(img_cv)
            
            # Detect faces and eyes
            metrics.eyes_open, metrics.face_count, metrics.face_regions = self.detect_eyes_open(img_cv)
            
            # Compute face blur scores if faces detected
            if metrics.face_count > 0:
                metrics.face_blur_scores = self.compute_face_blur(img_cv, metrics.face_regions)
            
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