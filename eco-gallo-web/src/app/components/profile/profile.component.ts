import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './profile.component.html',
  styleUrls: ['./profile.component.css']
})
export class ProfileComponent implements OnInit {
  user: any = null;
  isEditing: boolean = false;
  
  formData = {
    username: '',
    email: '',
    password: ''
  };

  message: string = '';
  errorMessage: string = '';

  constructor(
    private router: Router,
    private authService: AuthService
  ) {}

  ngOnInit(): void {
    const storedUser = localStorage.getItem('user');
    if (storedUser) {
      this.user = JSON.parse(storedUser);
      this.formData.username = this.user.username || '';
      this.formData.email = this.user.email || '';
    }
  }

  updateProfile(): void {
    this.message = '';
    this.errorMessage = '';

    this.authService.updateProfile(this.user.id, this.formData).subscribe({
      next: (res) => {
        this.message = res.message;
        
        // Actualizar datos locales del usuario
        this.user = { ...this.user, ...res.user };
        localStorage.setItem('user', JSON.stringify(this.user));
        
        // Limpiar contraseña y salir del modo edición
        this.formData.password = '';
        this.isEditing = false;
      },
      error: (err) => {
        this.errorMessage = err.error?.message || 'Error al actualizar el perfil';
      }
    });
  }

  cancelEdit(): void {
    // Restaurar los campos con la información actual del usuario
    this.formData.username = this.user.username;
    this.formData.email = this.user.email;
    this.formData.password = '';
    this.errorMessage = '';
    this.isEditing = false;
  }

  logout(): void {
    this.authService.logout();
    alert('Sesión cerrada correctamente');
    this.router.navigate(['/login']);
  }
}
