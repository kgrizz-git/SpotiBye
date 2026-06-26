# Phase 2: Frontend Development

> **Project Context**: This is Phase 2 of the SpotiBye backend-frontend split project. See [`project-summary-overview.md`](project-summary-overview.md) for the complete project overview, timeline, and architecture details.

## Who Runs This Code
- **Frontend Developer**: Responsible for implementing all Phase 2 tasks
- **UI/UX Designer**: May provide design specifications and user experience guidance
- **QA Engineer**: Will test user interface and user interactions
- **Product Manager**: May review feature implementations and user workflows

## How This Code Will Be Used
- **Development**: Frontend runs locally on port 3000 during development
- **Testing**: User interface tested manually and with automated testing tools
- **Production**: Deployed as static files to CDN or web server
- **User Access**: End users interact with the web interface in their browsers

## Phase Goals
- Create a modern web-based frontend to replace the Kivy desktop app
- Implement all existing UI functionality in a web interface
- Establish communication with backend API
- Ensure responsive design and good user experience
- Implement proper state management for async operations
- Create a maintainable and scalable frontend architecture

## Things to Be Careful About
- **State Management**: Frontend needs to handle async operations and loading states properly
- **Authentication Flow**: Must integrate seamlessly with backend's token-based auth system
- **Data Handling**: Large datasets need proper pagination and virtualization to avoid performance issues
- **Error Display**: User-friendly error messages from API responses, not technical details
- **Performance**: Avoid blocking UI during long-running operations like playlist analysis
- **Browser Compatibility**: Ensure consistent behavior across modern browsers
- **Mobile Responsiveness**: Design should work on mobile and desktop viewports
- **Accessibility**: Follow WCAG guidelines for accessibility

## Technology Stack Recommendation
- **Framework**: React 18 with TypeScript
- **Styling**: TailwindCSS with responsive design
- **State Management**: Zustand (lightweight) or Redux Toolkit (complex state)
- **HTTP Client**: Axios with interceptors
- **UI Components**: Headless UI + custom components
- **Build Tool**: Vite for fast development and builds
- **Testing**: Jest + React Testing Library
- **Code Quality**: ESLint + Prettier + TypeScript

## Implementation Checklist


**Instructions**: Mark completed tasks with `[x]` instead of `[ ]`. Do not delete completed tasks - they serve as a record of progress. Update this checklist as work progresses.

### 2.1 Project Structure Setup
- [ ] Create `frontend/` directory at project root
- [ ] Initialize React + TypeScript project with Vite
- [ ] Install core dependencies: React, TypeScript, TailwindCSS, Axios
- [ ] Install development dependencies: ESLint, Prettier, Jest, Testing Library
- [ ] Set up folder structure:
  - `src/components/` (reusable UI components)
  - `src/pages/` (route-level components)
  - `src/services/` (API client functions)
  - `src/hooks/` (custom React hooks)
  - `src/utils/` (utility functions)
  - `src/types/` (TypeScript type definitions)
  - `src/store/` (state management)
  - `src/assets/` (static assets)
- [ ] Configure TypeScript strict mode and path mapping
- [ ] Set up TailwindCSS with responsive breakpoints
- [ ] Configure ESLint and Prettier for consistent code style

### 2.2 API Client Development
- [ ] Create `frontend/src/services/api.ts` with Axios configuration
- [ ] Configure base URL and default headers
- [ ] Implement request interceptors for auth token injection
- [ ] Implement response interceptors for error handling
- [ ] Create `frontend/src/services/auth.ts` for authentication API calls
- [ ] Create `frontend/src/services/playlists.ts` for playlist API calls
- [ ] Create `frontend/src/services/analysis.ts` for track analysis API calls
- [ ] Create `frontend/src/services/export.ts` for export functionality
- [ ] Add retry logic for failed requests with exponential backoff
- [ ] Implement request cancellation for component unmounts
- [ ] Create TypeScript interfaces for all API responses

### 2.3 Authentication Implementation
- [ ] Create login page with Spotify OAuth integration
- [ ] Implement token storage (localStorage with security considerations)
- [ ] Create auth context/store for global authentication state
- [ ] Add automatic token refresh before expiration
- [ ] Implement logout functionality with proper cleanup
- [ ] Create protected routes that redirect to login if unauthenticated
- [ ] Add loading states during authentication operations
- [ ] Handle authentication errors gracefully
- [ ] Create auth hooks for easy access to auth state

### 2.4 Core UI Components
- [ ] Create layout components (Header, Sidebar, Main content area)
- [ ] Create reusable UI components:
  - Button (with loading states)
  - Input (with validation)
  - Modal/Dialog
  - Card/Tile
  - Table/List
  - Progress indicators
  - Toast notifications
- [ ] Create loading components and spinners for different contexts
- [ ] Create error display components with appropriate severity levels
- [ ] Create data display components (tables with sorting, virtual lists)
- [ ] Create form components with validation
- [ ] Implement consistent design system with proper spacing and colors

### 2.5 Page Implementation
- [ ] Create login page with OAuth integration
- [ ] Create main dashboard page with overview
- [ ] Create playlist listing page with search and filtering
- [ ] Create playlist detail page with track listing
- [ ] Create export configuration page with options
- [ ] Create export progress page with real-time updates
- [ ] Create settings page for user preferences
- [ ] Create error pages (404, 500, etc.)
- [ ] Implement navigation between pages
- [ ] Add breadcrumb navigation for deep pages

### 2.6 State Management
- [ ] Set up global state store (Zustand recommended for simplicity)
- [ ] Create auth state slice with user info and tokens
- [ ] Create playlist data state slice with caching
- [ ] Create export job state slice with progress tracking
- [ ] Create UI state slice (loading, errors, modals, etc.)
- [ ] Implement proper state persistence where needed
- [ ] Add state selectors for efficient re-renders
- [ ] Create state middleware for logging and persistence
- [ ] Test state management with various scenarios

### 2.7 Data Handling and Performance
- [ ] Implement virtual scrolling for large track lists
- [ ] Add pagination for playlist collections
- [ ] Implement debounced search to reduce API calls
- [ ] Add data caching in frontend to reduce redundant requests
- [ ] Implement optimistic updates for better UX
- [ ] Add loading skeletons for better perceived performance
- [ ] Implement proper cleanup of subscriptions and timers
- [ ] Add memory leak prevention for long-running operations
- [ ] Test performance with large datasets (1000+ tracks)
