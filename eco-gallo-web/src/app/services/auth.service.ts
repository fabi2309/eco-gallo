import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private apiUrl = 'http://localhost:5000/api/auth';

  constructor(private http: HttpClient) {}

  register(userData: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/register`, userData);
  }

  login(credentials: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/login`, credentials);
  }

  // Método para actualizar el perfil
  updateProfile(id: number, userData: any): Observable<any> {
    return this.http.put(`${this.apiUrl}/profile/${id}`, userData);
  }

  getPostById(id: string | number): Observable<any> {
  return this.http.get(`${this.apiUrl}/${id}`); // O `${this.apiUrl}/posts/${id}` según cómo manejes tus rutas
}
}