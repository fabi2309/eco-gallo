const express = require('express');
const cors = require('cors');
const { Sequelize, DataTypes } = require('sequelize');

const app = express();

// Middlewares
app.use(cors());
app.use(express.json());

// Configuración de SQLite (crea un archivo local llamado database.sqlite)
const sequelize = new Sequelize({
  dialect: 'sqlite',
  storage: './database.sqlite',
  logging: false
});

// Exportar sequelize para usarlo en los modelos
module.exports = sequelize;

// Importar modelos y rutas (se cargan después de definir la conexión)
const User = require('./models/User');
const Post = require('./models/Post');

app.use('/api/auth', require('./routes/auth.routes'));
app.use('/api/posts', require('./routes/posts.routes'));

app.get('/', (req, res) => {
  res.send('API de ECO-GALLO con SQLite funcionando 🚀');
});

const PORT = process.env.PORT || 5000;

// Sincronizar base de datos y arrancar servidor
sequelize.sync({ alter: true })
  .then(() => {
    console.log('Base de datos SQLite sincronizada 📁');
    app.listen(PORT, () => {
      console.log(`Servidor corriendo en el puerto ${PORT}`);
    });
  })
  .catch((error) => {
    console.error('Error al conectar con SQLite:', error);
  });