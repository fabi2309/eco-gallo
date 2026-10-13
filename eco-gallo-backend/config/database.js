const { Sequelize } = require('sequelize');

// Configuración de Sequelize para SQLite local
const sequelize = new Sequelize({
  dialect: 'sqlite',
  storage: './database.sqlite',
  logging: false
});

module.exports = sequelize;