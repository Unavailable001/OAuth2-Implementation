import { Injectable,signal,computed } from '@angular/core';
import {PortalUser} from './auth-api';

@Injectable({
  providedIn: 'root',
})
export class AuthState {

  // Stores the currently logged-in user
  private readonly currentUser = signal<PortalUser | null>(null);

  // Public read-only access to user information
  readonly user = this.currentUser.asReadonly();

  // Automatically calculates authentication status
  readonly isAuthenticated = computed(
    () => this.currentUser() !== null
  );

   // Store user information after successful login
  setUser(user: PortalUser): void {
    this.currentUser.set(user);
  }

  // Clear user information after logout
  clearUser(): void {
    this.currentUser.set(null);
  }
}
