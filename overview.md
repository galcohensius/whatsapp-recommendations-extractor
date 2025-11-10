# Project Overview

## What It Does

WhatsApp Recommendations Extractor is a web application that processes WhatsApp chat exports and VCF contact files to extract service provider recommendations. Users upload a ZIP file containing their chat history and contacts, and the system:

1. **Extracts** recommendations from chat messages
2. **Matches** contacts from VCF files
3. **Enhances** data with OpenAI (optional)
4. **Displays** results in an interactive, searchable interface

## Architecture

### Frontend (GitHub Pages)
- **upload.html** - File upload interface with drag-and-drop
- **results.html** - Interactive results display with search/filter
- **api.js** - API client for backend communication

### Backend (Render)
- **FastAPI** - REST API with async processing
- **PostgreSQL** - Session and results storage
- **Background Tasks** - Asynchronous file processing
- **Auto-cleanup** - Expires data after 1 day

### Processing Pipeline
1. Extract ZIP → Parse VCF files + a single TXT file
2. Extract recommendations from chat messages
3. Match VCF contacts mentioned in chats
4. Include unmentioned VCF files
5. Data cleanup and deduplication
6. Optional OpenAI enhancement
7. Store results in database

## Current Features

✅ **File Upload** - Drag-and-drop ZIP upload (max 5MB)  
✅ **Session Tracking** - Unique session IDs for each upload  
✅ **Status Polling** - Real-time processing status updates  
✅ **Results Display** - Searchable, filterable table with Hebrew support  
✅ **Click-to-call** - Phone numbers as clickable links  
✅ **OpenAI Enhancement** - Optional AI-powered data enrichment  
✅ **Auto-cleanup** - Automatic data expiration (1 day retention)  
✅ **Error Handling** - Timeout protection (30 min max)  

---

## Suggested Improvements

### 🚀 Features

**User Experience**
- [ ] **Progress indicators** - Show detailed processing steps (parsing VCF, extracting recommendations, etc.)
- [ ] **Download results** - Export results as CSV/JSON
- [ ] **Share results** - Generate shareable links (with optional password)
- [ ] **Multiple uploads** - Allow users to upload multiple ZIPs and merge results
- [ ] **Result history** - Show previous uploads for same session
- [ ] **Dark mode** - Toggle between light/dark themes
- [ ] **Mobile optimization** - Better responsive design for mobile devices

**Data Processing**
- [ ] **Batch processing** - Process multiple files in parallel
- [ ] **Incremental updates** - Re-upload to add/update recommendations
- [ ] **Duplicate detection** - Better deduplication across uploads
- [ ] **Data validation** - Pre-upload validation of ZIP contents
- [ ] **File preview** - Show ZIP contents before processing
- [ ] **Processing queue** - Queue system for multiple concurrent uploads

**Recommendations**
- [ ] **Service categories** - Auto-categorize services (plumber, electrician, etc.)
- [ ] **Rating system** - Allow users to rate recommendations
- [ ] **Notes/annotations** - Add personal notes to recommendations
- [ ] **Favorites** - Mark favorite service providers
- [ ] **Contact integration** - Direct integration with phone contacts
- [ ] **Recommendation sources** - Show which chat/contact provided the recommendation

### 🔒 Security & Authentication

- [ ] **OAuth login** - Google/GitHub authentication (as planned)
- [ ] **User accounts** - Persistent user profiles
- [ ] **Private sessions** - Encrypt sensitive data
- [ ] **Rate limiting** - Prevent abuse (if needed)
- [ ] **File scanning** - Virus/malware scanning for uploads
- [ ] **API authentication** - API keys for programmatic access

### 📊 Analytics & Monitoring

- [ ] **Usage analytics** - Track uploads, processing times, errors
- [ ] **Performance metrics** - Monitor API response times
- [ ] **Error tracking** - Sentry or similar for error monitoring
- [ ] **User feedback** - In-app feedback form
- [ ] **Processing statistics** - Show stats (files processed, recommendations found, etc.)

### 🛠️ Technical Improvements

**Backend**
- [ ] **Caching** - Redis for session caching
- [ ] **WebSockets** - Real-time status updates instead of polling
- [ ] **File storage** - S3/cloud storage for uploaded files (instead of temp files)
- [ ] **Database optimization** - Add indexes, connection pooling improvements
- [ ] **API versioning** - Version the API (`/api/v1/...`)
- [ ] **OpenAPI docs** - Enhanced API documentation
- [ ] **Testing** - Unit tests, integration tests
- [ ] **Logging** - Structured logging (JSON logs)

**Frontend**
- [ ] **Framework** - Consider React/Vue for better state management
- [ ] **PWA** - Progressive Web App for offline support
- [ ] **Service Worker** - Cache API responses
- [ ] **Error boundaries** - Better error handling
- [ ] **Accessibility** - ARIA labels, keyboard navigation
- [ ] **Internationalization** - Support multiple languages

**DevOps**
- [ ] **CI/CD** - GitHub Actions for automated testing/deployment
- [ ] **Docker** - Containerize the application
- [ ] **Environment configs** - Separate dev/staging/prod configs
- [ ] **Monitoring** - Uptime monitoring, health checks
- [ ] **Backup strategy** - Automated database backups
- [ ] **Load testing** - Test under load

### 📱 Integration

- [ ] **WhatsApp Web API** - Direct integration (if available)
- [ ] **Calendar integration** - Add appointments with service providers
- [ ] **Maps integration** - Show service provider locations
- [ ] **Email notifications** - Notify when processing completes
- [ ] **SMS notifications** - Optional SMS alerts
- [ ] **Export formats** - PDF, Excel, Google Sheets export

### 🎨 UI/UX Enhancements

- [ ] **Onboarding** - Welcome tour for first-time users
- [ ] **Empty states** - Better empty state designs
- [ ] **Loading skeletons** - Skeleton screens instead of spinners
- [ ] **Animations** - Smooth transitions and micro-interactions
- [ ] **Toast notifications** - Better notification system
- [ ] **Keyboard shortcuts** - Power user shortcuts
- [ ] **Bulk actions** - Select multiple recommendations for actions

---

## Priority Recommendations

### High Priority
1. **OAuth Authentication** - User accounts and persistent data
2. **Download/Export** - Users want to save their results
3. **Better error messages** - More descriptive error handling
4. **Mobile optimization** - Many users will use mobile devices

### Medium Priority
1. **WebSockets for real-time updates** - Better UX than polling
2. **Service categories** - Better organization of recommendations
3. **Result history** - Track previous uploads
4. **Testing** - Ensure reliability as project grows

### Low Priority
1. **Dark mode** - Nice-to-have feature
2. **Analytics** - Useful but not critical
3. **PWA** - Advanced feature for power users

---

## Technical Debt

- [ ] Consolidate duplicate code between `main.py` and `backend/services.py`
- [ ] Add type hints throughout codebase
- [ ] Document API endpoints more thoroughly
- [ ] Add input validation/sanitization
- [ ] Improve error messages with context
- [ ] Refactor large functions into smaller, testable units

