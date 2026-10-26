import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = 'http://localhost:5000/api';

  constructor(private http: HttpClient) {}

  register(data: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/auth/register`, data);
  }

  login(data: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/auth/login`, data);
  }

  getPosts(): Observable<any> {
    return this.http.get(`${this.baseUrl}/posts`);
  }

  // <-- IMPORTANTE: Nuevo método añadido para ver los detalles -->
  getPostById(id: string): Observable<any> {
    return this.http.get(`${this.baseUrl}/posts/${id}`);
  }

  createPost(postData: FormData): Observable<any> {
    return this.http.post(`${this.baseUrl}/posts`, postData);
  }

  sendMessage(data: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/messages`, data);
  }

  updatePost(id: number, postData: FormData): Observable<any> {
    return this.http.put(`${this.baseUrl}/posts/${id}`, postData);
  }

  deletePost(id: number): Observable<any> {
    return this.http.delete(`${this.baseUrl}/posts/${id}`);
  }
}