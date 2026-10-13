import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './register.component.html',
  styleUrls: ['./register.component.css']
})
export class RegisterComponent {
  user = { username: '', email: '', password: '', userType: 'student', kardexImage: '' };
  errorMessage = '';
  successMessage = '';

  constructor(private api: ApiService, private router: Router) {}

  onRegister() {
    this.api.register(this.user).subscribe({
      next: (res: any) => {
        this.successMessage = res.message;
        setTimeout(() => this.router.navigate(['/login']), 3000);
      },
      error: (err: any) => {
        this.errorMessage = err.error.message || 'Error al registrarse';
      }
    });
  }
}