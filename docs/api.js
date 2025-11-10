/**
 * API client for WhatsApp Recommendations Extractor backend.
 */

// Default API base URL - update this to your backend URL
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';

/**
 * Upload a zip file to the backend.
 * @param {File} file - The zip file to upload
 * @returns {Promise<{session_id: string, status: string}>}
 */
async function uploadFile(file) {
    // Validate file size (5MB)
    const maxSize = 5 * 1024 * 1024; // 5MB in bytes
    if (file.size > maxSize) {
        throw new Error(`File size exceeds 5MB limit. File is ${(file.size / 1024 / 1024).toFixed(2)}MB`);
    }
    
    // Validate file type
    if (!file.name.endsWith('.zip')) {
        throw new Error('Only .zip files are allowed');
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${API_BASE_URL}/api/upload`, {
        method: 'POST',
        body: formData
    });
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(error.detail || `Upload failed with status ${response.status}`);
    }
    
    return await response.json();
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
 * @param {number} maxPollingTime - Maximum time to poll in milliseconds (default: 30 minutes)
 * @param {number} pollInterval - Interval between polls in milliseconds (default: 2 seconds)
 * @returns {Promise<{status: string}>}
 */
async function pollStatus(sessionId, onStatusUpdate = null, maxPollingTime = 30 * 60 * 1000, pollInterval = 2000) {
    const startTime = Date.now();
    
    while (true) {
        const elapsed = Date.now() - startTime;
        if (elapsed > maxPollingTime) {
            throw new Error('Polling timeout exceeded');
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

