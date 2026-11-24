import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';

import 'api_client.dart';

class PhotoPickerService {
  final _picker = ImagePicker();
  Future<List<XFile>> _recovered = Future.value([]);
  void startRecovery() {
    // Keep errors as data until the editor opens, avoiding an unhandled future.
    _recovered = _recover();
  }

  Future<List<XFile>> _recover() async {
    try {
      final response = await _picker.retrieveLostData();
      return response.files ?? [];
    } on PlatformException {
      return [];
    } on MissingPluginException {
      return [];
    }
  }

  Future<List<XFile>> takeRecovered() async {
    final result = _recovered;
    _recovered = Future.value([]);
    return result;
  }

  Future<List<XFile>> pick({int limit = 5}) => _picker.pickMultiImage(
    limit: limit,
    maxWidth: 1920,
    maxHeight: 1920,
    imageQuality: 85,
    requestFullMetadata: false,
  );
}

Future<void> validatePhotos(
  List<XFile> photos, {
  required int maxCount,
  required int maxBytes,
}) async {
  if (photos.length > maxCount) {
    throw ApiException('Puedes seleccionar hasta $maxCount fotos.');
  }
  var total = 0;
  for (final photo in photos) {
    final size = await photo.length();
    total += size;
    if (size == 0 || size > maxBytes) {
      throw ApiException(
        'Cada foto debe ocupar entre 1 byte y ${maxBytes ~/ (1024 * 1024)} MB.',
      );
    }
    final header = await photo
        .openRead(0, size < 12 ? size : 12)
        .expand((b) => b)
        .toList();
    bool starts(List<int> signature) =>
        header.length >= signature.length &&
        Iterable<int>.generate(signature.length)
            .every((i) => header[i] == signature[i]);
    final jpeg = starts([255, 216, 255]);
    final png = starts([137, 80, 78, 71, 13, 10, 26, 10]);
    final webp =
        header.length >= 12 &&
        starts([82, 73, 70, 70]) &&
        header[8] == 87 &&
        header[9] == 69 &&
        header[10] == 66 &&
        header[11] == 80;
    if (!jpeg && !png && !webp) {
      throw const ApiException('Selecciona fotos JPG, PNG o WebP.');
    }
  }
  if (total > 24 * 1024 * 1024) {
    throw const ApiException('Las fotos juntas deben ocupar menos de 24 MB.');
  }
}
