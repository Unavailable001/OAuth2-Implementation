
import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthState } from '../../auth/auth-state';
import { AuthFlow } from '../../auth/auth-flow';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css'
})
export class Dashboard {

  authState = inject(AuthState);
  private authFlow = inject(AuthFlow);
  private readonly router = inject(Router);

  logout(): void {
    this.authFlow.logout().subscribe({
      next: () => {
        void this.router.navigateByUrl('/login');
      },
      error: error => {
        console.error('Logout failed:', error);
      }
    });
  }
}
