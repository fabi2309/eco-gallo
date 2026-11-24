class Student {
  const Student({
    required this.id,
    required this.name,
    required this.email,
    required this.carrera,
    required this.centro,
  });
  final int id;
  final String name, email, carrera, centro;
  factory Student.fromJson(Map<String, dynamic> json) => Student(
    id: json['id'] as int,
    name: json['name'] as String? ?? '',
    email: json['email'] as String? ?? '',
    carrera: json['carrera'] as String? ?? '',
    centro: json['centro'] as String? ?? 'General',
  );
}

class Post {
  const Post({
    required this.id,
    required this.title,
    required this.description,
    required this.category,
    required this.tipo,
    required this.priceCents,
    required this.condition,
    required this.status,
    required this.images,
    required this.author,
    required this.centro,
  });
  final int id, priceCents;
  final String title, description, category, tipo, condition, status, centro;
  final List<String> images;
  final Student author;
  factory Post.fromJson(Map<String, dynamic> json) => Post(
    id: json['id'] as int,
    title: json['title'] as String,
    description: json['description'] as String? ?? '',
    category: json['category'] as String,
    tipo: json['tipo'] as String,
    priceCents: json['price_cents'] as int? ?? 0,
    condition: json['condition'] as String? ?? '',
    status: json['status'] as String,
    centro: json['centro'] as String? ?? 'General',
    images: List<String>.from(json['images'] as List? ?? []),
    author: Student.fromJson(json['author'] as Map<String, dynamic>),
  );

  String get priceLabel => tipo == 'donacion'
      ? 'Gratis'
      : tipo == 'trueque'
      ? 'Trueque'
      : '\$${(priceCents / 100).toStringAsFixed(priceCents % 100 == 0 ? 0 : 2)} MXN';
  String get typeLabel => switch (tipo) {
    'donacion' => 'Donación',
    'trueque' => 'Trueque',
    _ => 'Venta',
  };
  bool get canEdit => const ['active', 'paused', 'pending'].contains(status);
  String get statusLabel => switch (status) {
    'pending' => 'En revisión',
    'active' => 'Disponible',
    'paused' => 'Pausado',
    'reserved' => 'Reservado',
    'sold' => 'Vendido',
    'removed' => 'Retirado',
    _ => 'No disponible',
  };
}

class PostPage {
  const PostPage(this.posts, this.page, this.pages, this.total);
  final List<Post> posts;
  final int page, pages, total;
  factory PostPage.fromJson(Map<String, dynamic> json) => PostPage(
    (json['posts'] as List)
        .map((p) => Post.fromJson(p as Map<String, dynamic>))
        .toList(),
    json['page'] as int,
    json['pages'] as int,
    json['total'] as int,
  );
}
