module.exports = {
  apps: [
    {
      name: "hot-boxed-pie",
      script: "server.js",
      instances: 1, // Can be increased for load balancing
      exec_mode: "cluster",
      watch: false, // Disable watch in production
      max_memory_restart: "500M",

      // Environment variables
      env: {
        NODE_ENV: "production",
        PORT: 3000,
      },

      // Error logging
      error_file: "logs/error.log",
      out_file: "logs/out.log",
      log_file: "logs/combined.log",
      time: true, // Add timestamps to logs

      // Restart behavior
      exp_backoff_restart_delay: 100,
      max_restarts: 10,

      // Resource management
      node_args: "--max-old-space-size=500", // Limit heap size to 500MB

      // Graceful shutdown
      kill_timeout: 3000, // Give the app 3 seconds to handle remaining requests
    },
  ],
};
