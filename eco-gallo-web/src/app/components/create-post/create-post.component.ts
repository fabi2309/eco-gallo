import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-create-post',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './create-post.component.html',
  styleUrls: ['./create-post.component.css']
})
export class CreatePostComponent {
  postData = {
    title: '',
    description: '',
    category: '',
    physicalState: '',
    price: null as number | null
  };
  selectedFile: File | null = null;
  errorMessage = '';

  constructor(private api: ApiService, private router: Router) {}

  onFileSelected(event: any) {
    if (event.target.files.length > 0) {
      this.selectedFile = event.target.files[0];
    }
  }

  onSubmit() {
    const formData = new FormData();
    formData.append('title', this.postData.title);
    formData.append('description', this.postData.description);
    formData.append('category', this.postData.category);
    formData.append('physicalState', this.postData.physicalState);

    if (this.postData.price !== null) {
      formData.append('price', this.postData.price.toString());
    }

    const storedUser = localStorage.getItem('user');
    if (storedUser) {
      const user = JSON.parse(storedUser);
      formData.append('authorId', user.id);
    }

    if (this.selectedFile) {
      formData.append('image', this.selectedFile);
    }

    this.api.createPost(formData).subscribe({
      next: () => {
        alert('¡Publicación creada con éxito!');
        this.router.navigate(['/home']);
      },
      error: (err: any) => {
        console.error('Error al publicar:', err);
        this.errorMessage = err.error?.message || 'Error al crear la publicación';
      }
    });
  }
}