// PM2 Configuration - IAlex Sales Agent
// Uso: pm2 start ecosystem.config.js
// Verificar: pm2 status | pm2 logs | pm2 restart all

const path = require('path');
const projectRoot = __dirname;

module.exports = {
  apps: [
    {
      name: 'ialex-bridge',
      script: 'index.js',
      cwd: path.join(projectRoot, 'whatsapp-bridge'),
      interpreter: 'node',
      watch: false,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      env: {
        NODE_ENV: 'production',
        PORT: 8090
      },
      log_file: path.join(projectRoot, 'logs', 'pm2-bridge.log'),
      error_file: path.join(projectRoot, 'logs', 'pm2-bridge-error.log'),
      out_file: path.join(projectRoot, 'logs', 'pm2-bridge-out.log'),
      time: true,
    },
    {
      name: 'ialex-webhook',
      script: 'agent/webhook_server.py',
      cwd: projectRoot,
      interpreter: path.join(projectRoot, 'venv', 'Scripts', 'python.exe'),
      watch: false,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      env: {
        PYTHONIOENCODING: 'utf-8',
        PYTHONPATH: projectRoot
      },
      log_file: path.join(projectRoot, 'logs', 'pm2-webhook.log'),
      error_file: path.join(projectRoot, 'logs', 'pm2-webhook-error.log'),
      out_file: path.join(projectRoot, 'logs', 'pm2-webhook-out.log'),
      time: true,
    }
  ]
};
