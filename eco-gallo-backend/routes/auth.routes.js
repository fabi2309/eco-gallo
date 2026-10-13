const express = require('express');
const router = express.Router();
const bcrypt = require('bcryptjs');
const User = require('../models/User');

// Ruta de Registro
router.post('/register', async (req, res) => {
  try {
    const { username, email, password, userType, kardexImage } = req.body;

    if (userType === 'student') {
      const studentEmailRegex = /^al\d{6}@edu\.uaa\.mx$/;
      if (!studentEmailRegex.test(email)) {
        return res.status(400).json({ message: 'El correo de estudiante debe ser institucional (ej. al350114@edu.uaa.mx)' });
      }
    } else if (userType === 'alumni') {
      if (!kardexImage) {
        return res.status(400).json({ message: 'Los egresados deben subir una captura de su kárdex para validación.' });
      }
    }

    const hashedPassword = await bcrypt.hash(password, 10);

    const newUser = await User.create({
      username,
      email,
      password: hashedPassword,
      userType: userType || 'student',
      kardexImage: kardexImage || null,
      isApproved: userType === 'student' ? true : false
    });

    res.status(201).json({ 
      message: userType === 'student' 
        ? 'Registro exitoso.' 
        : 'Registro en revisión. El administrador evaluará tu kárdex y recibirás respuesta en 3 días.' 
    });
  } catch (err) {
    console.error('Error en registro:', err);
    res.status(500).json({ message: 'Error en el servidor al registrar', error: err.message });
  }
});

// Ruta de Inicio de Sesión
router.post('/login', async (req, res) => {
  try {
    const { email, password } = req.body;
    
    const user = await User.findOne({ where: { email } });
    if (!user) {
      return res.status(400).json({ message: 'Usuario no encontrado' });
    }

    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) {
      return res.status(400).json({ message: 'Credenciales incorrectas' });
    }

    if (user.userType === 'alumni' && !user.isApproved) {
      return res.status(403).json({ message: 'Tu cuenta de egresado está pendiente de revisión por el administrador.' });
    }

    res.json({ message: 'Inicio de sesión exitoso', user });
  } catch (err) {
    console.error('Error en login:', err);
    res.status(500).json({ message: 'Error en el servidor al iniciar sesión', error: err.message });
  }
});

// Ruta para actualizar perfil del usuario
router.put('/profile/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const { username, email, password } = req.body;

    const user = await User.findByPk(id);
    if (!user) {
      return res.status(404).json({ message: 'Usuario no encontrado' });
    }

    // Actualizar nombre de usuario si se proporciona
    if (username) user.username = username;

    // Actualizar email si cambia (y validar en caso de estudiante)
    if (email && email !== user.email) {
      if (user.userType === 'student') {
        const studentEmailRegex = /^al\d{6}@edu\.uaa\.mx$/;
        if (!studentEmailRegex.test(email)) {
          return res.status(400).json({ message: 'El correo debe ser institucional (ej. al350114@edu.uaa.mx)' });
        }
      }
      user.email = email;
    }

    // Actualizar contraseña si la envió
    if (password && password.trim() !== '') {
      user.password = await bcrypt.hash(password, 10);
    }

    await user.save();

    // Retornar usuario actualizado sin la contraseña
    const updatedUserData = user.toJSON();
    delete updatedUserData.password;

    res.json({ message: 'Perfil actualizado con éxito', user: updatedUserData });
  } catch (err) {
    console.error('Error al actualizar perfil:', err);
    res.status(500).json({ message: 'Error en el servidor al actualizar perfil', error: err.message });
  }
});

module.exports = router;