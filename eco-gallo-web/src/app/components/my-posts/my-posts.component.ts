import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-my-posts',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './my-posts.component.html',
  styleUrls: ['./my-posts.component.css']
})
export class MyPostsComponent implements OnInit {
  myPosts: any[] = [];
  selectedPost: any = null; // Guarda la publicación en edición
  selectedFile: File | null = null;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.loadMyPosts();
  }

  loadMyPosts(): void {
    const storedUser = localStorage.getItem('user');
    if (!storedUser) return;
    const user = JSON.parse(storedUser);

    this.api.getPosts().subscribe({
      next: (posts: any[]) => {
        this.myPosts = posts.filter(p => p.authorId === user.id || p.author?.id === user.id);
      },
      error: (err) => {
        console.error('Error al cargar tus publicaciones', err);
      }
    });
  }

  // Abrir formulario de edición
  editPost(post: any): void {
    this.selectedPost = { ...post };
    this.selectedFile = null;
  }

  // Cancelar edición
  cancelEdit(): void {
    this.selectedPost = null;
    this.selectedFile = null;
  }

  // Capturar nueva imagen si la sube
  onFileSelected(event: any): void {
    if (event.target.files.length > 0) {
      this.selectedFile = event.target.files[0];
    }
  }

  deletePost(id: number) {
  if (confirm('¿Estás segura de que deseas eliminar esta publicación?')) {
    this.api.deletePost(id).subscribe({
      next: () => {
        // Filtra la lista localmente para que desaparezca de inmediato
        this.myPosts = this.myPosts.filter(post => post.id !== id);
      },
      error: (err) => console.error('Error al eliminar:', err)
    });
  }
}

  // Guardar cambios
  savePost(): void {
    if (!this.selectedPost) return;

    const formData = new FormData();
    formData.append('title', this.selectedPost.title);
    formData.append('description', this.selectedPost.description);
    formData.append('category', this.selectedPost.category);
    formData.append('physicalState', this.selectedPost.physicalState);
    formData.append('price', this.selectedPost.price);

    if (this.selectedFile) {
      formData.append('image', this.selectedFile);
    }

    this.api.updatePost(this.selectedPost.id, formData).subscribe({
      next: () => {
        alert('Publicación actualizada correctamente');
        this.selectedPost = null;
        this.loadMyPosts();
      },
      error: (err) => {
        console.error('Error al actualizar la publicación', err);
        alert('Ocurrió un error al intentar actualizar');
      }
    });
  }
}