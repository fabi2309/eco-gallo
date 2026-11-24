import '../core/api_client.dart';
import '../models/models.dart';

import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

class CatalogRepository {
  const CatalogRepository(this.api);
  final ApiClient api;
  Future<PostPage> list({
    String query = '',
    String category = '',
    String tipo = '',
    int page = 1,
    bool mine = false,
  }) async => PostPage.fromJson(
    await api.get('/api/posts', {
      'q': query,
      'category': category,
      'tipo': tipo,
      'page': '$page',
      'per_page': '20',
      if (mine) 'mine': '1',
    }),
  );
  Future<Post> detail(int id) async => Post.fromJson(
    (await api.get('/api/posts/$id'))['post'] as Map<String, dynamic>,
  );
  Future<int> save(
    Map<String, String> fields,
    List<XFile> photos, {
    int? id,
  }) async {
    final files = <http.MultipartFile>[];
    for (var i = 0; i < photos.length; i++) {
      files.add(
        await http.MultipartFile.fromPath(
          'images',
          photos[i].path,
          filename:
              'material-$i.${photos[i].name.split('.').last.toLowerCase()}',
        ),
      );
    }
    final result = await api.multipart(
      id == null ? 'POST' : 'PUT',
      id == null ? '/api/posts' : '/api/posts/$id',
      fields,
      files,
    );
    return id ?? result['id'] as int;
  }

  Future<void> pause(int id, bool paused) async {
    await api.post('/api/posts/$id/pause', {'paused': paused});
  }
}
