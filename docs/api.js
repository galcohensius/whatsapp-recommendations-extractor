/**
 * API client for WhatsApp Recommendations Extractor backend.
 */

// Default API base URL - update this to your backend URL
const API_BASE_URL = 'https://whatsapp-recommendations-api.onrender.com';

/**
 * Upload a zip file to the backend.
 * @param {File} file - The zip file to upload
 * @param {Function} onProgress - Optional callback for upload progress (receives percentage 0-100)
 * @returns {{promise: Promise<{session_id: string, status: string}>, abort: Function}} Object with promise and abort function
 */
function uploadFile(file, onProgress = null) {
    // Validate file size (5MB)
    const maxSize = 5 * 1024 * 1024; // 5MB in bytes
    if (file.size > maxSize) {
        return {
            promise: Promise.reject(new Error(`File size exceeds 5MB limit. File is ${(file.size / 1024 / 1024).toFixed(2)}MB`)),
            abort: () => {}
        };
    }
    
    // Validate file type
    if (!file.name.endsWith('.zip')) {
        return {
            promise: Promise.reject(new Error('Only .zip files are allowed')),
            abort: () => {}
        };
    }
    
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append('file', file);
    
    const promise = new Promise((resolve, reject) => {
        // Track upload progress
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable && onProgress) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                onProgress(percentComplete);
            }
        });
        
        // Handle completion
        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const response = JSON.parse(xhr.responseText);
                    resolve(response);
                } catch (e) {
                    reject(new Error('Invalid response from server'));
                }
            } else {
                try {
                    const error = JSON.parse(xhr.responseText);
                    reject(new Error(error.detail || `Upload failed with status ${xhr.status}`));
                } catch (e) {
                    reject(new Error(`Upload failed with status ${xhr.status}`));
                }
            }
        });
        
        // Handle errors
        xhr.addEventListener('error', () => {
            reject(new Error('Network error during upload'));
        });
        
        xhr.addEventListener('abort', () => {
            reject(new Error('Upload was aborted'));
        });
        
        // Start upload
        xhr.open('POST', `${API_BASE_URL}/api/upload`);
        xhr.send(formData);
    });
    
    return {
        promise: promise,
        abort: () => {
            xhr.abort();
        }
    };
}

/**
 * Get processing status for a session.
 * @param {string} sessionId - The session ID
 * @returns {Promise<{status: string, error_message?: string}>}
 */
async function getStatus(sessionId) {
    const response = await fetch(`${API_BASE_URL}/api/status/${sessionId}`);
    
    if (!response.ok) {
        if (response.status === 404) {
            throw new Error('Session not found');
        }
        const error = await response.json().catch(() => ({ detail: 'Status check failed' }));
        throw new Error(error.detail || `Status check failed with status ${response.status}`);
    }
    
    return await response.json();
}

/**
 * Get processed results for a session.
 * @param {string} sessionId - The session ID
 * @returns {Promise<{recommendations: Array, openai_enhanced: boolean, created_at: string}>}
 */
async function getResults(sessionId) {
    const response = await fetch(`${API_BASE_URL}/api/results/${sessionId}`);
    
    if (!response.ok) {
        if (response.status === 404) {
            throw new Error('Results not found');
        }
        if (response.status === 410) {
            throw new Error('Results have expired');
        }
        if (response.status === 202) {
            const data = await response.json().catch(() => ({ detail: 'Processing not complete' }));
            throw new Error(data.detail || 'Processing not complete');
        }
        const error = await response.json().catch(() => ({ detail: 'Failed to fetch results' }));
        throw new Error(error.detail || `Failed to fetch results with status ${response.status}`);
    }
    
    return await response.json();
}

/**
 * Poll for status updates until processing is complete or timeout.
 * @param {string} sessionId - The session ID
 * @param {Function} onStatusUpdate - Callback function called on each status update
 * @param {number} maxPollingTime - Maximum time to poll in milliseconds (default: 2 hours - gives buffer after backend 2 hour timeout)
 * @param {number} pollInterval - Interval between polls in milliseconds (default: 2 seconds)
 * @returns {Promise<{status: string}>}
 */
async function pollStatus(sessionId, onStatusUpdate = null, maxPollingTime = 2 * 60 * 60 * 1000, pollInterval = 2000) {
    const startTime = Date.now();
    
    while (true) {
        const elapsed = Date.now() - startTime;
        if (elapsed > maxPollingTime) {
            const minutes = Math.floor(maxPollingTime / 60000);
            throw new Error(`Polling timeout exceeded after ${minutes} minutes. The processing may still be running on the server. Please refresh the page or try again later.`);
        }
        
        try {
            const status = await getStatus(sessionId);
            
            if (onStatusUpdate) {
                onStatusUpdate(status);
            }
            
            if (status.status === 'completed') {
                return status;
            }
            
            if (status.status === 'error' || status.status === 'timeout') {
                throw new Error(status.error_message || `Processing failed with status: ${status.status}`);
            }
            
            // Wait before next poll
            await new Promise(resolve => setTimeout(resolve, pollInterval));
            
        } catch (error) {
            // If it's a status error (not found, etc.), rethrow
            if (error.message.includes('not found') || error.message.includes('expired')) {
                throw error;
            }
            // Otherwise, continue polling
            await new Promise(resolve => setTimeout(resolve, pollInterval));
        }
    }
}

