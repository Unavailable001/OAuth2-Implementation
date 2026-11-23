import { Injectable, inject } from '@angular/core';
import {
  AuthApi,
  CurrentUserResponse
} from './auth-api';

import {
  Observable,
  of,
  throwError
} from 'rxjs';
import { AuthState } from './auth-state';


import {
  catchError,
  tap,
  map
} from 'rxjs/operators';



@Injectable({
  providedIn: 'root',
})
export class AuthFlow {
  private authApi = inject(AuthApi);

  private authState = inject(AuthState);

  // --------------------------------
  // 1. Start Google login
  // --------------------------------

  login(): void {
    this.authApi.startGoogleLogin();
  }

  // --------------------------------
  // 2. Restore the backend session
  // --------------------------------



  loadSession(): Observable<CurrentUserResponse | null> {
    return this.authApi.getCurrentUser().pipe(
      map(response => {
        this.authState.setUser(response.user);
        return response;
      }),
      catchError(error => {
        if (error.status !== 401) {
          return throwError(() => error);
        }

        this.authState.clearUser();
        return of(null);
      })
    );
  }




  // --------------------------------
  // 3. Check backend session
  // --------------------------------

  getCurrentUser() {

    return this.authApi.getCurrentUser();

  }

  // --------------------------------
  // 4. Logout
  // --------------------------------

  logout() {

    return this.authApi.logout().pipe(

      tap(() => {
        this.authState.clearUser();
      })

    );


  }


}
