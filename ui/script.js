// State management
let reportData = null;
let currentBurst = 0;
let currentCluster = 0;
let currentImage = 0;
let allImageElements = [];

// DOM elements
const fileInput = document.getElementById('fileInput');
const loadBtn = document.getElementById('loadBtn');
const exportBtn = document.getElementById('exportBtn');
const burstList = document.getElementById('burstList');
const summary = document.getElementById('summary');
const clustersContainer = document.getElementById('clusters');
const modal = document.getElementById('imageModal');
const modalImg = document.getElementById('modalImg');
const modalCaption = document.getElementById('modalCaption');
const splitter = document.getElementById('splitter');
const previewPanel = document.getElementById('previewPanel');

// Event listeners
loadBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', handleFileLoad);
exportBtn.addEventListener('click', exportReport);

// Splitter resize functionality
let isResizing = false;
let startX = 0;
let startWidth = 400;

splitter.addEventListener('mousedown', (e) => {
    isResizing = true;
    startX = e.clientX;
    startWidth = previewPanel.offsetWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
});

document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    
    const diff = startX - e.clientX;
    const newWidth = startWidth + diff;
    
    // Respect min and max constraints
    const minWidth = 250;
    const maxWidth = window.innerWidth * 0.6;
    
    if (newWidth >= minWidth && newWidth <= maxWidth) {
        previewPanel.style.width = newWidth + 'px';
    }
});

document.addEventListener('mouseup', () => {
    if (isResizing) {
        isResizing = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        
        // Save preference to localStorage
        localStorage.setItem('previewPanelWidth', previewPanel.offsetWidth);
    }
});

// Restore saved width on load
window.addEventListener('DOMContentLoaded', () => {
    const savedWidth = localStorage.getItem('previewPanelWidth');
    if (savedWidth) {
        previewPanel.style.width = savedWidth + 'px';
    }
});

// Auto-load report.json if served by our server
window.addEventListener('DOMContentLoaded', async () => {
    // Check if a specific report is requested via URL parameter
    const urlParams = new URLSearchParams(window.location.search);
    const reportName = urlParams.get('report');
    
    let reportUrl = '/report.json';
    if (reportName) {
        // Load specific report from output directory
        reportUrl = `/output/${reportName}/report.json`;
    }
    
    try {
        const response = await fetch(reportUrl);
        if (response.ok) {
            const report = await response.json();
            console.log(`Loaded report from ${reportUrl}`);
            reportData = report;
            
            // Enable export button
            exportBtn.disabled = false;
            
            // Initialize UI
            renderSummary();
            renderBurstList();
            
            // Show first burst if available
            if (report.bursts && report.bursts.length > 0) {
                selectBurst(0);
                // Auto-select first image
                setTimeout(() => {
                    if (allImageElements.length > 0) {
                        selectImage(0, 0);
                    }
                }, 100);
            }
        }
    } catch (err) {
        console.log('Could not auto-load report - use Load button to select file');
    }
});

document.querySelector('.close').addEventListener('click', () => {
    modal.style.display = 'none';
});

window.addEventListener('click', (e) => {
    if (e.target === modal) {
        modal.style.display = 'none';
    }
});

// File handling
async function handleFileLoad(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    try {
        const text = await file.text();
        reportData = JSON.parse(text);
        
        // Enable export button
        exportBtn.disabled = false;
        
        // Initialize UI
        renderSummary();
        renderBurstList();
        
        // Show first burst if available
        if (reportData.bursts && reportData.bursts.length > 0) {
            selectBurst(0);
            // Auto-select first image
            setTimeout(() => {
                if (allImageElements.length > 0) {
                    selectImage(0, 0);
                }
            }, 100);
        }
    } catch (error) {
        alert('Error loading report file: ' + error.message);
    }
}

// Export updated report
function exportReport() {
    if (!reportData) return;
    
    const dataStr = JSON.stringify(reportData, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = 'report.updated.json';
    a.click();
    
    URL.revokeObjectURL(url);
}

// Render summary statistics
function renderSummary() {
    if (!reportData) return;
    
    const totalImages = reportData.images.length;
    const totalClusters = reportData.hash_clusters.length;
    const totalBursts = reportData.bursts ? reportData.bursts.length : 0;
    
    summary.innerHTML = `
        <h3>Summary</h3>
        <div class="summary-stats">
            <div class="stat-item">
                <div class="stat-label">Total Images</div>
                <div class="stat-value">${totalImages}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Bursts</div>
                <div class="stat-value">${totalBursts}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Clusters</div>
                <div class="stat-value">${totalClusters}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Winners</div>
                <div class="stat-value">${totalClusters}</div>
            </div>
        </div>
    `;
}

// Render burst list in sidebar
function renderBurstList() {
    if (!reportData || !reportData.bursts) return;
    
    burstList.innerHTML = '';
    
    // Filter out empty bursts (no clusters)
    const nonEmptyBursts = [];
    reportData.bursts.forEach((burst, index) => {
        const burstClusters = reportData.hash_clusters.filter(c => c.burst_id === index);
        if (burstClusters.length > 0) {
            nonEmptyBursts.push({burst, index, clusters: burstClusters});
        }
    });
    
    nonEmptyBursts.forEach(({burst, index, clusters}) => {
        const li = document.createElement('li');
        li.className = 'burst-item';
        li.dataset.burstId = index;
        
        li.innerHTML = `
            <div class="burst-name">Burst ${index + 1}</div>
            <div class="burst-info">${burst.length} images • ${clusters.length} clusters</div>
        `;
        
        li.addEventListener('click', () => selectBurst(index));
        burstList.appendChild(li);
    });
}

// Select and display a burst
function selectBurst(burstId) {
    currentBurst = burstId;
    currentCluster = 0;
    currentImage = 0;
    
    // Update sidebar selection
    document.querySelectorAll('.burst-item').forEach(item => {
        item.classList.toggle('active', parseInt(item.dataset.burstId) === burstId);
    });
    
    // Render clusters for this burst
    renderClusters(burstId);
}

// Render clusters for a burst
function renderClusters(burstId) {
    if (!reportData) return;
    
    // Filter clusters for this burst
    const burstClusters = reportData.hash_clusters.filter(c => c.burst_id === burstId);
    
    if (burstClusters.length === 0) {
        clustersContainer.innerHTML = `
            <div class="empty-state">
                <h3>No clusters in this burst</h3>
                <p>This burst has no photo clusters.</p>
            </div>
        `;
        return;
    }
    
    clustersContainer.innerHTML = '';
    allImageElements = [];
    
    burstClusters.forEach(cluster => {
        const clusterDiv = document.createElement('div');
        clusterDiv.className = 'cluster';
        
        // Cluster header
        const header = document.createElement('div');
        header.className = 'cluster-header';
        
        // Check if cluster spans multiple bursts
        let clusterInfo = `Cluster ${cluster.cluster_id + 1}`;
        if (cluster.burst_ids && cluster.burst_ids.length > 1) {
            clusterInfo += ` (spans bursts ${cluster.burst_ids.map(b => b + 1).join(', ')})`;
        }
        
        header.innerHTML = `
            <div class="cluster-title">${clusterInfo}</div>
            <div class="cluster-badge">${cluster.members.length} images</div>
        `;
        clusterDiv.appendChild(header);
        
        // Images grid
        const imagesGrid = document.createElement('div');
        imagesGrid.className = 'cluster-images';
        
        cluster.members.forEach((imagePath, index) => {
            const imageData = reportData.images.find(img => img.path === imagePath);
            const score = cluster.scores[index];
            const isWinner = imagePath === cluster.winner;
            
            const card = createImageCard(imageData, score, isWinner, cluster.cluster_id, burstClusters.indexOf(cluster), index);
            imagesGrid.appendChild(card);
        });
        
        clusterDiv.appendChild(imagesGrid);
        clustersContainer.appendChild(clusterDiv);
    });
}

// Create an image card
function createImageCard(imageData, score, isWinner, clusterId, clusterIndex, imageIndex) {
    const card = document.createElement('div');
    card.className = 'image-card' + (isWinner ? ' winner' : '');
    card.dataset.clusterId = clusterId;
    card.dataset.clusterIndex = clusterIndex;
    card.dataset.imageIndex = imageIndex;
    
    // Store reference for keyboard navigation
    allImageElements.push({card, imageData, score, isWinner, clusterId, clusterIndex, imageIndex});
    
    // Image container
    const imgContainer = document.createElement('div');
    imgContainer.className = 'image-container';
    imgContainer.addEventListener('click', () => {
        selectImage(clusterIndex, imageIndex);
    });
    
    // Try to load image thumbnail (prefer thumbnail_path if available)
    const img = document.createElement('img');
    // Use thumbnail if available, otherwise fallback to original
    const imageSrc = imageData.thumbnail_path || imageData.path;
    img.src = getImageUrl(imageSrc);
    img.alt = getFileName(imageData.path);
    img.dataset.originalPath = imageData.path; // Store original path for reference
    img.onerror = () => {
        // If thumbnail fails, try original path as fallback
        if (imageSrc !== imageData.path && imageData.path) {
            img.src = getImageUrl(imageData.path);
            img.onerror = () => {
                img.style.display = 'none';
                imgContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">Image not accessible</div>';
            };
        } else {
            img.style.display = 'none';
            imgContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">Image not accessible</div>';
        }
    };
    imgContainer.appendChild(img);
    
    if (isWinner) {
        const badge = document.createElement('div');
        badge.className = 'winner-badge';
        badge.textContent = 'Winner';
        imgContainer.appendChild(badge);
    }
    
    card.appendChild(imgContainer);
    
    // Image info
    const info = document.createElement('div');
    info.className = 'image-info';
    
    // File name
    const name = document.createElement('div');
    name.className = 'image-name';
    name.textContent = getFileName(imageData.path);
    info.appendChild(name);
    
    // Score
    const scoreDiv = document.createElement('div');
    scoreDiv.className = 'score';
    scoreDiv.textContent = `Score: ${score.toFixed(3)}`;
    info.appendChild(scoreDiv);
    
    // Metrics
    const metrics = document.createElement('div');
    metrics.className = 'image-metrics';
    
    // Blur status
    if (imageData.is_blurry !== undefined) {
        const blurMetric = document.createElement('span');
        blurMetric.className = 'metric' + (imageData.is_blurry ? ' warning' : ' good');
        blurMetric.textContent = imageData.is_blurry ? 'Blurry' : 'Sharp';
        metrics.appendChild(blurMetric);
    } else {
        // Fallback to old sharpness metric
        const sharpMetric = document.createElement('span');
        sharpMetric.className = 'metric' + (imageData.sharpness > 100 ? ' good' : '');
        sharpMetric.textContent = `Sharp: ${imageData.sharpness.toFixed(0)}`;
        metrics.appendChild(sharpMetric);
    }
    
    // Motion blur indicator
    if (imageData.has_motion_blur) {
        const motionMetric = document.createElement('span');
        motionMetric.className = 'metric warning';
        motionMetric.textContent = 'Motion blur';
        metrics.appendChild(motionMetric);
    }
    
    // Eyes open
    if (imageData.face_count > 0) {
        const eyesMetric = document.createElement('span');
        eyesMetric.className = 'metric' + (imageData.eyes_open > 0.5 ? ' good' : ' warning');
        eyesMetric.textContent = `Eyes: ${(imageData.eyes_open * 100).toFixed(0)}%`;
        metrics.appendChild(eyesMetric);
    }
    
    // Face blur for portraits
    if (imageData.face_blur_scores && imageData.face_blur_scores.length > 0) {
        const avgFaceBlur = imageData.face_blur_scores.reduce((a, b) => a + b) / imageData.face_blur_scores.length;
        const faceBlurMetric = document.createElement('span');
        faceBlurMetric.className = 'metric' + (avgFaceBlur > 0.5 ? ' good' : ' warning');
        faceBlurMetric.textContent = `Face blur: ${(avgFaceBlur * 100).toFixed(0)}%`;
        metrics.appendChild(faceBlurMetric);
    }
    
    // Faces
    if (imageData.face_count > 0) {
        const facesMetric = document.createElement('span');
        facesMetric.className = 'metric';
        facesMetric.textContent = `${imageData.face_count} face${imageData.face_count > 1 ? 's' : ''}`;
        metrics.appendChild(facesMetric);
    }
    
    info.appendChild(metrics);
    
    // Promote button
    if (!isWinner) {
        const promoteBtn = document.createElement('button');
        promoteBtn.className = 'promote-btn';
        promoteBtn.textContent = 'Promote to Winner';
        promoteBtn.addEventListener('click', () => promoteImage(imageData.path, clusterId));
        info.appendChild(promoteBtn);
    }
    
    card.appendChild(info);
    return card;
}

// Promote an image to winner
function promoteImage(imagePath, clusterId) {
    if (!reportData) return;
    
    // Find the cluster
    const cluster = reportData.hash_clusters.find(c => c.cluster_id === clusterId);
    if (!cluster) return;
    
    // Update winner
    cluster.winner = imagePath;
    
    // Re-render current burst
    renderClusters(currentBurst);
}

// Show image modal
function showModal(imageData) {
    modal.style.display = 'block';
    // Use thumbnail for modal too (it's high enough resolution)
    const imageSrc = imageData.thumbnail_path || imageData.path;
    modalImg.src = getImageUrl(imageSrc);
    modalImg.onerror = () => {
        // Fallback to original if thumbnail fails
        if (imageSrc !== imageData.path) {
            modalImg.src = getImageUrl(imageData.path);
        }
    };
    modalCaption.innerHTML = `
        <strong>${getFileName(imageData.path)}</strong><br>
        ${imageData.width}×${imageData.height} • 
        Sharpness: ${imageData.sharpness.toFixed(0)} • 
        Score: ${imageData.score.toFixed(3)}
    `;
}

// Select an image and show preview
function selectImage(clusterIndex, imageIndex) {
    currentCluster = clusterIndex;
    currentImage = imageIndex;
    
    // Update visual selection
    let selectedCard = null;
    document.querySelectorAll('.image-card').forEach(card => {
        const isSelected = parseInt(card.dataset.clusterIndex) === clusterIndex && 
                          parseInt(card.dataset.imageIndex) === imageIndex;
        card.classList.toggle('selected', isSelected);
        if (isSelected) {
            selectedCard = card;
        }
    });
    
    // Scroll selected card into view if needed
    if (selectedCard) {
        const content = document.getElementById('content');
        const cardRect = selectedCard.getBoundingClientRect();
        const contentRect = content.getBoundingClientRect();
        
        // Check if card is outside visible area
        if (cardRect.top < contentRect.top || cardRect.bottom > contentRect.bottom) {
            selectedCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
    
    // Find the image data
    const element = allImageElements.find(el => 
        el.clusterIndex === clusterIndex && el.imageIndex === imageIndex
    );
    
    if (element) {
        showPreview(element.imageData, element.score, element.isWinner);
    }
}

// Show image in preview panel
function showPreview(imageData, score, isWinner) {
    const previewImg = document.getElementById('previewImage');
    const previewInfo = document.getElementById('previewInfo');
    
    // Load image
    const imageSrc = imageData.thumbnail_path || imageData.path;
    previewImg.src = getImageUrl(imageSrc);
    previewImg.classList.add('loaded');
    previewImg.onerror = () => {
        if (imageSrc !== imageData.path) {
            previewImg.src = getImageUrl(imageData.path);
            previewImg.onerror = () => {
                previewImg.classList.remove('loaded');
            };
        } else {
            previewImg.classList.remove('loaded');
        }
    };
    
    // Show info
    let infoHtml = `<h4>${getFileName(imageData.path)}</h4>`;
    
    infoHtml += `
        <div class="info-row">
            <span class="info-label">Score</span>
            <span class="info-value">${score.toFixed(3)}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Status</span>
            <span class="info-value">${isWinner ? 'Winner' : 'Similar'}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Dimensions</span>
            <span class="info-value">${imageData.width} × ${imageData.height}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Sharpness</span>
            <span class="info-value">${imageData.sharpness.toFixed(0)}</span>
        </div>
    `;
    
    if (imageData.blur_score !== undefined) {
        infoHtml += `
            <div class="info-row">
                <span class="info-label">Blur Score</span>
                <span class="info-value">${(imageData.blur_score * 100).toFixed(0)}% ${imageData.is_blurry ? '(Blurry)' : ''}</span>
            </div>
        `;
    }
    
    if (imageData.has_motion_blur) {
        infoHtml += `
            <div class="info-row">
                <span class="info-label">Motion Blur</span>
                <span class="info-value">Detected</span>
            </div>
        `;
    }
    
    if (imageData.face_count > 0) {
        infoHtml += `
            <div class="info-row">
                <span class="info-label">Faces</span>
                <span class="info-value">${imageData.face_count}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Eyes Open</span>
                <span class="info-value">${(imageData.eyes_open * 100).toFixed(0)}%</span>
            </div>
        `;
    }
    
    previewInfo.innerHTML = infoHtml;
}

// Keyboard navigation
document.addEventListener('keydown', (e) => {
    if (!reportData) return;
    
    const burstClusters = reportData.hash_clusters.filter(c => c.burst_id === currentBurst);
    if (burstClusters.length === 0) return;
    
    switch(e.key) {
        case 'ArrowLeft':
            e.preventDefault();
            navigateImage(-1);
            break;
        case 'ArrowRight':
            e.preventDefault();
            navigateImage(1);
            break;
        case 'ArrowUp':
            e.preventDefault();
            navigateBurst(-1);
            break;
        case 'ArrowDown':
            e.preventDefault();
            navigateBurst(1);
            break;
        case ' ':
            e.preventDefault();
            promoteCurrentImage();
            break;
        case '[':
            e.preventDefault();
            adjustPreviewWidth(-50);
            break;
        case ']':
            e.preventDefault();
            adjustPreviewWidth(50);
            break;
    }
});

// Navigate between images
function navigateImage(direction) {
    const burstClusters = reportData.hash_clusters.filter(c => c.burst_id === currentBurst);
    if (burstClusters.length === 0) return;
    
    const currentClusterImages = burstClusters[currentCluster]?.members.length || 0;
    
    if (direction > 0) {
        // Move right
        if (currentImage < currentClusterImages - 1) {
            currentImage++;
        } else if (currentCluster < burstClusters.length - 1) {
            currentCluster++;
            currentImage = 0;
        } else {
            // Wrap to beginning
            currentCluster = 0;
            currentImage = 0;
        }
    } else {
        // Move left
        if (currentImage > 0) {
            currentImage--;
        } else if (currentCluster > 0) {
            currentCluster--;
            currentImage = burstClusters[currentCluster].members.length - 1;
        } else {
            // Wrap to end
            currentCluster = burstClusters.length - 1;
            currentImage = burstClusters[currentCluster].members.length - 1;
        }
    }
    
    selectImage(currentCluster, currentImage);
}

// Navigate between bursts
function navigateBurst(direction) {
    const burstItems = Array.from(document.querySelectorAll('.burst-item'));
    if (burstItems.length === 0) return;
    
    const currentIndex = burstItems.findIndex(item => 
        parseInt(item.dataset.burstId) === currentBurst
    );
    
    let newIndex = currentIndex + direction;
    if (newIndex < 0) newIndex = burstItems.length - 1;
    if (newIndex >= burstItems.length) newIndex = 0;
    
    const newBurstId = parseInt(burstItems[newIndex].dataset.burstId);
    selectBurst(newBurstId);
    
    // Auto-select first image in new burst
    setTimeout(() => {
        if (allImageElements.length > 0) {
            selectImage(0, 0);
        }
    }, 100);
}

// Promote current image to winner
function promoteCurrentImage() {
    const element = allImageElements.find(el => 
        el.clusterIndex === currentCluster && el.imageIndex === currentImage
    );
    
    if (element && !element.isWinner) {
        promoteImage(element.imageData.path, element.clusterId);
        // Re-select the same image after re-render
        setTimeout(() => selectImage(currentCluster, currentImage), 100);
    }
}

// Adjust preview panel width
function adjustPreviewWidth(delta) {
    const currentWidth = previewPanel.offsetWidth;
    const newWidth = currentWidth + delta;
    const minWidth = 250;
    const maxWidth = window.innerWidth * 0.6;
    
    if (newWidth >= minWidth && newWidth <= maxWidth) {
        previewPanel.style.width = newWidth + 'px';
        localStorage.setItem('previewPanelWidth', newWidth);
    }
}

// Helper functions
function getFileName(path) {
    return path.split(/[\\/]/).pop();
}

function getImageUrl(path) {
    // Handle different path formats
    if (path.startsWith('http://') || path.startsWith('https://')) {
        return path;
    } else if (path.includes('thumbnails/')) {
        // Check if we're viewing a specific report
        const urlParams = new URLSearchParams(window.location.search);
        const reportName = urlParams.get('report');
        
        if (reportName) {
            // Prepend the output directory path
            return `/output/${reportName}/${path}`;
        } else if (path.startsWith('/')) {
            return path;
        } else {
            return '/' + path;
        }
    } else if (path.startsWith('file://')) {
        // File protocol - only works if browser allows it
        return path;
    } else if (path.startsWith('/')) {
        // Absolute path - try file protocol
        return 'file://' + path;
    } else {
        // Assume relative path
        return '/' + path;
    }
}