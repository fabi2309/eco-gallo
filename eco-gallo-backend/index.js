const express = require('express');
const cors = require('cors');
const sequelize = require('./config/database'); 
const authRoutes = require('./routes/auth.routes');
const postsRoutes = require('./routes/posts.routes');
const messageRoutes = require('./routes/messages.routes');
const Post = require('./models/Post'); 
const User = require('./models/User'); // <-- IMPORTANTE: Se agregó el modelo de Usuario

const app = express();

app.use(cors());
app.use(express.json());

// Hacer pública la carpeta de imágenes para que se puedan ver en el frontend
app.use('/uploads', express.static('uploads'));

// Registrar las rutas del sistema
app.use('/api/auth', authRoutes);
app.use('/api/posts', postsRoutes);
app.use('/api/messages', messageRoutes);

// <-- IMPORTANTE: Se definieron las relaciones entre las tablas -->
Post.belongsTo(User, { foreignKey: 'authorId' });
User.hasMany(Post, { foreignKey: 'authorId' });

const PORT = process.env.PORT || 5000;

// Sincronizar base de datos y levantar el servidor
sequelize.sync().then(async () => {
  console.log('Base de datos SQLite sincronizada correctamente');

  // Insertar productos de prueba automáticamente si la tabla está vacía
  try {
    const count = await Post.count();
    if (count === 0) {
      await Post.bulkCreate([
        {
          title: 'Libro de Cálculo Vectorial',
          description: 'Libro en buen estado para ingenierías, edición reciente.',
          category: 'Libros',
          physicalState: 'Usado',
          price: 250,
          image: null,
          authorId: 1
        },
        {
          title: 'Protoboard y Cables Dupont',
          description: 'Kit básico para prácticas de circuitos digitales y sistemas electrónicos.',
          category: 'Herramientas',
          physicalState: 'Como nuevo',
          price: 120,
          image: null,
          authorId: 1
        },
        {
          title: 'Multímetro Digital',
          description: 'Ideal para mediciones de voltaje y corriente en laboratorio.',
          category: 'Electrónica',
          physicalState: 'Nuevo',
          price: 300,
          image: null,
          authorId: 1
        }
      ]);
      console.log('¡Productos de prueba insertados automáticamente!');
    }
  } catch (seedError) {
    console.error('Aviso al insertar productos de prueba:', seedError.message);
  }

  app.listen(PORT, () => {
    console.log(`Servidor corriendo en el puerto ${PORT}`);
  });
}).catch(err => {
  console.error('Error al conectar con la base de datos:', err);
});