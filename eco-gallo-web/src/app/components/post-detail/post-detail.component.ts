import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-post-detail',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './post-detail.component.html',
  styleUrls: ['./post-detail.component.css']
})
export class PostDetailComponent implements OnInit {
  post: any = null;

  constructor(private route: ActivatedRoute, private api: ApiService) {}

  ngOnInit(): void {
    const postId = this.route.snapshot.paramMap.get('id');
    if (postId) {
      this.api.getPostById(postId).subscribe({
        next: (data: any) => {
          this.post = data;
        },
        error: (err: any) => {
          console.error('Error al cargar el detalle del post:', err);
        }
      });
    }
  }

  // Método simulado para el botón de contacto
  contactarVendedor() {
    alert('Función de contacto simulada. ¡Pronto estará disponible!');
  }
}