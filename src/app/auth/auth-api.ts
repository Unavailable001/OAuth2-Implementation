import { Injectable, inject } from '@angular/core';

import {HttpClient,HttpHeaders} from '@angular/common/http';

import {Observable,of,map,tap,switchMap} from 'rxjs';


// --------------------------------
// 1. Backend URL
// --------------------------------

const API_BASE_URL = 'http://localhost:8000';


// --------------------------------
// 2. User interface
// --------------------------------

export interface PortalUser {

  provider: 'google';

  provider_user_id: string;

  email: string | null;

  email_verified?: boolean;

  name: string | null;

}


// --------------------------------
// 3. API response interfaces
// --------------------------------

export interface CurrentUserResponse {

  authenticated: boolean;

  user: PortalUser;

}


interface CsrfResponse {

  csrf_token: string;

}


export interface LogoutResponse {

  logged_out: boolean;

  message: string;

}


// --------------------------------
// 4. Authentication API service
// --------------------------------

@Injectable({
  providedIn: 'root',
})
export class AuthApi {
  // Dependency Injection

  private http = inject(HttpClient);


  // Keep CSRF token in memory only

  private csrfToken: string | null = null;


  startGoogleLogin(): void {
    window.location.assign(`${API_BASE_URL}/auth/login`);
  }

  // --------------------------------
  // 5. Get current authenticated user
  // --------------------------------

  getCurrentUser(): Observable<CurrentUserResponse> {

    return this.http.get<CurrentUserResponse>(

      `${API_BASE_URL}/auth/me`,

      {
        withCredentials: true
      }

    );

  }


  // --------------------------------
  // 6. Get CSRF token
  // --------------------------------

  getCsrfToken(
    forceRefresh = false
  ): Observable<string> {

    if (this.csrfToken && !forceRefresh) {

      return of(this.csrfToken);

    }


    return this.http.get<CsrfResponse>(

      `${API_BASE_URL}/auth/csrf`,

      {
        withCredentials: true
      }

    ).pipe(

      map(response => response.csrf_token),

      tap(token => {

        this.csrfToken = token;

      })

    );

  }


  // --------------------------------
  // 7. Logout
  // --------------------------------

  logout(): Observable<LogoutResponse> {

    return this.getCsrfToken(true).pipe(

      switchMap(csrfToken => {

        const headers = new HttpHeaders({

          'X-CSRF-Token': csrfToken

        });


        return this.http.post<LogoutResponse>(

          `${API_BASE_URL}/auth/logout`,

          {},

          {
            headers: headers,
            withCredentials: true
          }

        );

      }),

      tap(() => {

        this.csrfToken = null;

      })

    );

  }


}
