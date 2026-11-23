import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class UserApi {

  private http = inject(HttpClient);

  getPost() {
    return this.http.get(
      'https://jsonplaceholder.typicode.com/posts/1'
    );
  }
}
