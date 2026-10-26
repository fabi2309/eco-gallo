import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterModule, FormsModule],
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent implements OnInit {
  posts: any[] = [];
  filteredPosts: any[] = [];
  searchTerm: string = '';
  selectedCategory: string = '';

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    this.loadPosts();
  }

  loadPosts() {
    this.api.getPosts().subscribe({
      next: (data: any[]) => {
        this.posts = data.map(post => ({
          ...post,
          imageUrl: post.imageUrl ? (post.imageUrl.startsWith('http') ? post.imageUrl : `http://localhost:5000${post.imageUrl}`) : null
        }));
        this.filteredPosts = [...this.posts];
      },
      error: (err) => console.error('Error al cargar publicaciones:', err)
    });
  }

  filterPosts() {
    this.filteredPosts = this.posts.filter(post => {
      const matchesSearch = post.title.toLowerCase().includes(this.searchTerm.toLowerCase()) ||
                            post.description.toLowerCase().includes(this.searchTerm.toLowerCase());
      const matchesCategory = this.selectedCategory ? post.category === this.selectedCategory : true;
      return matchesSearch && matchesCategory;
    });
  }

  goToMyPosts() {
    // Redirige a la vista de tus publicaciones (ajusta la ruta '/my-posts' si es diferente en tu proyecto)
    this.router.navigate(['/my-posts']);
  }

  logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    this.router.navigate(['/login']);
  }
}