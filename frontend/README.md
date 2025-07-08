# MV Face Recognition - Frontend

**Primary Frontend for MV Face Recognition System**

This is the main frontend application built with SvelteKit, optimized for deployment on Cloudflare Workers with static generation. This frontend replaced the original Vue.js version and is currently deployed in production.

## 🚀 Features

- **Modern Svelte/SvelteKit Architecture**: Built with the latest Svelte ecosystem
- **Reactive State Management**: Uses Svelte stores instead of Pinia for state management
- **Responsive Design**: Mobile-first design with CSS Grid and Flexbox
- **Dark/Light Theme**: Automatic theme detection with manual toggle
- **Type Safety**: Full TypeScript support throughout the application
- **Real-time Updates**: WebSocket integration for live processing updates
- **File Upload**: Drag & drop video upload with progress tracking
- **Material Design**: Clean, modern UI inspired by Material Design principles

## 📁 Project Structure

```
frontend/
├── src/
│   ├── app.css                 # Global styles and CSS variables
│   ├── app.html               # HTML template
│   ├── lib/
│   │   ├── services/
│   │   │   └── api.ts         # API service layer
│   │   ├── stores/
│   │   │   ├── main.ts        # Main application store
│   │   │   ├── contestants.ts  # Contestants management store
│   │   │   └── videoProcessing.ts # Video processing store
│   │   └── types/
│   │       └── api.ts         # TypeScript type definitions
│   └── routes/
│       ├── +layout.svelte     # Main application layout
│       ├── +page.svelte       # Dashboard page
│       ├── video-processing/
│       │   └── +page.svelte   # Video processing page
│       ├── face-recognition/
│       │   └── +page.svelte   # Face recognition results
│       ├── analytics/
│       │   └── +page.svelte   # Analytics dashboard
│       └── settings/
│           └── +page.svelte   # Application settings
├── package.json
├── svelte.config.js
├── tsconfig.json
├── vite.config.ts
└── README.md
```

## 🔄 Migration from Vue.js

### Key Changes Made

1. **Framework Migration**:
   - Vue 3 Composition API → Svelte reactive statements
   - Vuetify components → Custom CSS components with utility classes
   - Vue Router → SvelteKit file-based routing
   - Pinia stores → Svelte writable/derived stores

2. **State Management**:
   ```javascript
   // Vue (Pinia)
   const store = useMainStore()
   const data = computed(() => store.dashboardStats)
   
   // Svelte
   import { dashboardStats } from '$lib/stores/main'
   $: data = $dashboardStats
   ```

3. **Component Structure**:
   ```svelte
   <!-- Vue template -->
   <template>
     <v-card>
       <v-card-title>{{ title }}</v-card-title>
     </v-card>
   </template>
   
   <!-- Svelte -->
   <div class="card">
     <h2>{title}</h2>
   </div>
   ```

4. **Reactive Data**:
   ```javascript
   // Vue
   const count = ref(0)
   const doubled = computed(() => count.value * 2)
   
   // Svelte
   let count = 0
   $: doubled = count * 2
   ```

### Benefits of Svelte Version

- **Smaller Bundle Size**: Svelte compiles to vanilla JavaScript, resulting in smaller bundles
- **Better Performance**: No virtual DOM overhead, direct DOM manipulation
- **Simpler State Management**: Built-in reactivity without external libraries
- **Less Boilerplate**: More concise syntax and less configuration needed
- **Better TypeScript Integration**: First-class TypeScript support

## 🛠️ Development Setup

### Prerequisites

- Node.js 18+ 
- npm or yarn or pnpm

### Installation

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install dependencies**:
   ```bash
   npm install
   # or
   yarn install
   # or
   pnpm install
   ```

3. **Start development server**:
   ```bash
   npm run dev
   # or
   yarn dev
   # or
   pnpm dev
   ```

4. **Open your browser**:
   Navigate to `http://localhost:5173`

### Build for Production

```bash
npm run build
npm run preview
```

## 🏗️ Architecture Overview

### Store Management

The application uses Svelte stores for state management:

- **Main Store** (`main.ts`): Application-wide state, system status, settings
- **Contestants Store** (`contestants.ts`): Contestant management and CRUD operations
- **Video Processing Store** (`videoProcessing.ts`): Video upload, processing jobs, results

### API Integration

The `ApiService` class handles all HTTP communications:

```typescript
// Example usage
import { ApiService } from '$lib/services/api'

const contestants = await ApiService.getContestants()
const job = await ApiService.processVideo(request)
```

### Routing

SvelteKit uses file-based routing:

- `/` → Dashboard (`+page.svelte`)
- `/video-processing` → Video upload and processing
- `/face-recognition` → Recognition results
- `/analytics` → Analytics dashboard
- `/settings` → Application settings

### Styling

The application uses:

- **CSS Custom Properties**: For theming and consistent colors
- **CSS Grid & Flexbox**: For responsive layouts
- **Component-scoped CSS**: Svelte's built-in style scoping
- **Utility Classes**: For common styling patterns

## 🎨 Theming

The app supports both light and dark themes:

```css
:root {
  --primary-color: #1976d2;
  --background-color: #fafafa;
  --surface-color: #ffffff;
  --text-primary: rgba(0, 0, 0, 0.87);
}

[data-theme="dark"] {
  --primary-color: #2196f3;
  --background-color: #121212;
  --surface-color: #1e1e1e;
  --text-primary: rgba(255, 255, 255, 0.87);
}
```

## 📱 Responsive Design

The frontend is fully responsive with:

- Mobile-first CSS approach
- Flexible grid layouts
- Touch-friendly interface elements
- Adaptive navigation (drawer on mobile)

## 🔧 Configuration

### API Endpoint

Configure the API endpoint in `vite.config.ts`:

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true
    }
  }
}
```

### Environment Variables

Create a `.env` file for environment-specific configuration:

```env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_WS_URL=ws://localhost:8000/ws
```

## 🧪 Testing

```bash
# Run type checking
npm run check

# Run linting
npm run lint

# Format code
npm run format
```

## 📦 Deployment

### Cloudflare Workers (Production)

This frontend is optimized for deployment on Cloudflare Workers:

1. **Build for static deployment**:
   ```bash
   npm run build
   ```

2. **Deploy to Cloudflare Workers**:
   ```bash
   # From project root
   cp -r frontend/build/* worker/public/
   wrangler deploy
   ```

3. **Live deployment**: https://mv-face-recognition.herballemon.workers.dev

### Configuration

The app uses `@sveltejs/adapter-static` for static site generation:

```javascript
// svelte.config.js
import adapter from '@sveltejs/adapter-static';

const config = {
  kit: {
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: 'index.html',
      precompress: false,
      strict: true
    })
  }
};
```

## 🔄 Migration Guide

If you're migrating from the Vue version:

1. **Store Usage**: Replace Pinia store imports with Svelte store imports
2. **Component Props**: Convert Vue props to Svelte component props
3. **Event Handling**: Replace Vue event handlers with Svelte event handlers
4. **Lifecycle**: Replace Vue lifecycle hooks with Svelte lifecycle functions
5. **Reactivity**: Convert Vue computed properties to Svelte reactive statements

## 🤝 Contributing

1. Follow the existing code style and patterns
2. Use TypeScript for all new components
3. Ensure responsive design principles
4. Test on both light and dark themes
5. Update this README if adding new features

## 📄 License

This project is part of the MV Face Recognition system. See the main project README for license information.

---

**Architecture**: This SvelteKit frontend is the primary application interface, deployed on Cloudflare Workers with static generation. The legacy Vue.js frontend has been archived and is no longer in active development.

**Deployment Status**: ✅ Live at https://mv-face-recognition.herballemon.workers.dev