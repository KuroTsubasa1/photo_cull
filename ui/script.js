// State management
let reportData = null;
let currentBurst = 0;

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

// Event listeners
loadBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', handleFileLoad);
exportBtn.addEventListener('click', exportReport);

// Auto-load report.json if served by our server
window.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('/report.json');
        if (response.ok) {
            const report = await response.json();
            console.log('Auto-loaded report.json from server');
            reportData = report;
            
            // Enable export button
            exportBtn.disabled = false;
            
            // Initialize UI
            renderSummary();
            renderBurstList();
            
            // Show first burst if available
            if (report.bursts && report.bursts.length > 0) {
                selectBurst(0);
            }
        }
    } catch (err) {
        console.log('Could not auto-load report.json - use Load button to select file');
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
    
    reportData.bursts.forEach((burst, index) => {
        const li = document.createElement('li');
        li.className = 'burst-item';
        li.dataset.burstId = index;
        
        // Count clusters in this burst
        const burstClusters = reportData.hash_clusters.filter(c => c.burst_id === index);
        
        li.innerHTML = `
            <div class="burst-name">Burst ${index + 1}</div>
            <div class="burst-info">${burst.length} images • ${burstClusters.length} clusters</div>
        `;
        
        li.addEventListener('click', () => selectBurst(index));
        burstList.appendChild(li);
    });
}

// Select and display a burst
function selectBurst(burstId) {
    currentBurst = burstId;
    
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
    
    burstClusters.forEach(cluster => {
        const clusterDiv = document.createElement('div');
        clusterDiv.className = 'cluster';
        
        // Cluster header
        const header = document.createElement('div');
        header.className = 'cluster-header';
        header.innerHTML = `
            <div class="cluster-title">Cluster ${cluster.cluster_id + 1}</div>
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
            
            const card = createImageCard(imageData, score, isWinner, cluster.cluster_id);
            imagesGrid.appendChild(card);
        });
        
        clusterDiv.appendChild(imagesGrid);
        clustersContainer.appendChild(clusterDiv);
    });
}

// Create an image card
function createImageCard(imageData, score, isWinner, clusterId) {
    const card = document.createElement('div');
    card.className = 'image-card' + (isWinner ? ' winner' : '');
    
    // Image container
    const imgContainer = document.createElement('div');
    imgContainer.className = 'image-container';
    imgContainer.addEventListener('click', () => showModal(imageData));
    
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

// Helper functions
function getFileName(path) {
    return path.split(/[\\/]/).pop();
}

function getImageUrl(path) {
    // Handle different path formats
    if (path.startsWith('http://') || path.startsWith('https://')) {
        return path;
    } else if (path.startsWith('thumbnails/')) {
        // Relative thumbnail path - will be served by our server
        return '/' + path;
    } else if (path.startsWith('/thumbnails/')) {
        // Already has leading slash
        return path;
    } else if (path.startsWith('file://')) {
        // File protocol - only works if browser allows it
        return path;
    } else if (path.startsWith('/')) {
        // Absolute path - try file protocol
        return 'file://' + path;
    } else {
        // Assume relative path
        return path;
    }
}