const express = require('express');
const router = express.Router();
const multer = require('multer');
const Post = require('../models/Post');
const User = require('../models/User'); // <-- Asegúrate de importar el modelo User para el include

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, 'uploads/');
  },
  filename: (req, file, cb) => {
    cb(null, Date.now() + '-' + file.originalname);
  }
});
const upload = multer({ storage });

// 1. Obtener todas las publicaciones
router.get('/', async (req, res) => {
  try {
    const posts = await Post.findAll();
    res.json(posts);
  } catch (err) {
    res.status(500).json({ message: 'Error al obtener publicaciones', error: err.message });
  }
});

// 2. OBTENER UN POST POR ID (¡IMPORTANTE: Debe ir ANTES de las rutas de actualización o conflicto de parámetros!)
router.get('/:id', async (req, res) => {
  try {
    const post = await Post.findByPk(req.params.id, {
      include: [{ model: User, attributes: ['username', 'email'] }]
    });
    if (!post) {
      return res.status(404).json({ message: 'Publicación no encontrada' });
    }
    res.json(post);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// 3. Crear una publicación
router.post('/', upload.single('image'), async (req, res) => {
  try {
    const { title, description, category, physicalState, price, authorId } = req.body;
    const imageUrl = req.file ? `/uploads/${req.file.filename}` : null;

    const newPost = await Post.create({
      title,
      description,
      category,
      physicalState,
      price: price ? Number(price) : null,
      image: imageUrl,
      authorId: authorId || 1
    });

    res.status(201).json({ message: 'Publicación creada con éxito', post: newPost });
  } catch (err) {
    console.error('Error detallado al crear post:', err);
    res.status(500).json({ message: 'Error en el servidor al publicar', error: err.message });
  }
});

// 4. Actualizar una publicación
router.put('/:id', upload.single('image'), async (req, res) => {
  try {
    const { title, description, category, physicalState, price } = req.body;
    const post = await Post.findByPk(req.params.id);
    
    if (!post) {
      return res.status(404).json({ message: 'Publicación no encontrada' });
    }

    const imageUrl = req.file ? `/uploads/${req.file.filename}` : post.image;

    await post.update({
      title: title || post.title,
      description: description || post.description,
      category: category || post.category,
      physicalState: physicalState || post.physicalState,
      price: price ? Number(price) : post.price,
      image: imageUrl
    });

    res.json({ message: 'Publicación actualizada con éxito', post });
  } catch (err) {
    res.status(500).json({ message: 'Error al actualizar la publicación', error: err.message });
  }
});

// 5. Eliminar una publicación
router.delete('/:id', async (req, res) => {
  try {
    const post = await Post.findByPk(req.params.id);
    
    if (!post) {
      return res.status(404).json({ message: 'Publicación no encontrada' });
    }

    await post.destroy();
    res.json({ message: 'Publicación eliminada correctamente' });
  } catch (err) {
    res.status(500).json({ message: 'Error al eliminar la publicación', error: err.message });
  }
});

module.exports = router;