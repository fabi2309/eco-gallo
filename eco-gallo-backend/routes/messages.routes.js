const express = require('express');
const router = express.Router();
const Message = require('../models/Message');

// Enviar mensaje a un usuario
router.post('/', async (req, res) => {
  try {
    const { senderId, receiverId, content } = req.body;
    const message = await Message.create({ senderId, receiverId, content });
    res.status(201).json(message);
  } catch (err) {
    res.status(500).json({ message: 'Error al enviar mensaje', error: err.message });
  }
});

// Obtener mensajes de un usuario
router.get('/:userId', async (req, res) => {
  try {
    const messages = await Message.findAll({
      where: { receiverId: req.params.userId }
    });
    res.json(messages);
  } catch (err) {
    res.status(500).json({ message: 'Error al obtener mensajes', error: err.message });
  }
});

module.exports = router;