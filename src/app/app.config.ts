import { ApplicationConfig, provideBrowserGlobalErrorListeners, provideAppInitializer, inject } from '@angular/core';
import { provideRouter } from '@angular/router';

import { routes } from './app.routes';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  requestLoggerInterceptorInterceptor
} from './interceptors/request-logger.interceptor-interceptor';
import { AuthFlow } from './auth/auth-flow';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideAppInitializer(() => {
      const authFlow = inject(AuthFlow);

      return new Promise<void>((resolve, reject) => {

        authFlow.loadSession().subscribe({
          next: () => resolve(),
          error: error => {
            console.error('Authentication initialization failed', error);
            reject(error);
          }
        });

      });
    }),
    provideRouter(routes),
    provideHttpClient(withInterceptors([requestLoggerInterceptorInterceptor]))
  ]
};
