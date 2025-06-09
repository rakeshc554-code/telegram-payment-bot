#!/bin/bash

# Production Deployment Script for Telegram Payment Bot
# This script sets up the production environment

set -e  # Exit on any error

echo "🚀 Starting production deployment for Telegram Payment Bot..."

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        echo "❌ This script should not be run as root for security reasons"
        exit 1
    fi
}

# Create necessary directories
setup_directories() {
    echo "📁 Creating directories..."
    mkdir -p logs
    mkdir -p receipts
    mkdir -p backups
    mkdir -p ssl
    echo "✅ Directories created"
}

# Install system dependencies
install_system_deps() {
    echo "📦 Installing system dependencies..."
    
    # Check if running on Ubuntu/Debian
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y python3-pip python3-venv postgresql postgresql-contrib redis-server nginx certbot python3-certbot-nginx
    elif command -v yum &> /dev/null; then
        # CentOS/RHEL
        sudo yum update -y
        sudo yum install -y python3-pip python3-venv postgresql-server postgresql-contrib redis nginx certbot python3-certbot-nginx
    else
        echo "❌ Unsupported operating system. Please install dependencies manually."
        exit 1
    fi
    
    echo "✅ System dependencies installed"
}

# Setup Python virtual environment
setup_python_env() {
    echo "🐍 Setting up Python environment..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install Python dependencies
    pip install -r requirements.txt
    
    echo "✅ Python environment setup complete"
}

# Setup PostgreSQL database
setup_database() {
    echo "🗄️ Setting up PostgreSQL database..."
    
    # Start PostgreSQL service
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    
    # Create database and user (interactive)
    echo "Creating database user and database..."
    echo "Please enter the details for your database setup:"
    
    read -p "Database name (default: telegram_bot): " DB_NAME
    DB_NAME=${DB_NAME:-telegram_bot}
    
    read -p "Database user (default: telegram_bot_user): " DB_USER
    DB_USER=${DB_USER:-telegram_bot_user}
    
    read -s -p "Database password: " DB_PASSWORD
    echo
    
    # Create user and database
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
    
    echo "✅ Database setup complete"
}

# Setup Redis
setup_redis() {
    echo "📊 Setting up Redis..."
    
    # Start Redis service
    sudo systemctl start redis-server
    sudo systemctl enable redis-server
    
    # Configure Redis for production
    sudo sed -i 's/# maxmemory <bytes>/maxmemory 256mb/' /etc/redis/redis.conf
    sudo sed -i 's/# maxmemory-policy noeviction/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf
    
    sudo systemctl restart redis-server
    
    echo "✅ Redis setup complete"
}

# Create environment configuration
setup_env_config() {
    echo "⚙️ Setting up environment configuration..."
    
    if [ ! -f ".env" ]; then
        echo "Creating .env file..."
        cat > .env << EOL
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
WEBHOOK_URL=https://yourdomain.com

# Database Configuration
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME
REDIS_URL=redis://localhost:6379/0

# PayPal Configuration
PAYPAL_CLIENT_ID=your_paypal_client_id_here
PAYPAL_CLIENT_SECRET=your_paypal_client_secret_here
PAYPAL_MODE=live

# Stripe Configuration
STRIPE_PUBLISHABLE_KEY=your_stripe_publishable_key_here
STRIPE_SECRET_KEY=your_stripe_secret_key_here
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret_here

# Security Configuration
SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -base64 32)

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password_here
FROM_EMAIL=your_email@gmail.com

# Mobile Money Configuration
MPESA_CONSUMER_KEY=your_mpesa_consumer_key_here
MPESA_CONSUMER_SECRET=your_mpesa_consumer_secret_here
MPESA_BUSINESS_SHORT_CODE=your_mpesa_business_short_code_here
MPESA_PASSKEY=your_mpesa_passkey_here
MPESA_ENVIRONMENT=sandbox
MPESA_CALLBACK_URL=\${WEBHOOK_URL}/webhook/mpesa

# MTN Mobile Money Configuration
MTN_SUBSCRIPTION_KEY=your_mtn_subscription_key_here
MTN_API_USER=your_mtn_api_user_here
MTN_API_KEY=your_mtn_api_key_here
MTN_ENVIRONMENT=sandbox

# Cryptocurrency Configuration
BITPAY_API_TOKEN=your_bitpay_api_token_here
BITPAY_ENVIRONMENT=test
BITPAY_NOTIFICATION_URL=\${WEBHOOK_URL}/webhook/bitpay
BITPAY_REDIRECT_URL=\${WEBHOOK_URL}/bitpay/redirect

# CoinGate Configuration
COINGATE_API_TOKEN=your_coingate_api_token_here
COINGATE_ENVIRONMENT=sandbox
COINGATE_CALLBACK_URL=\${WEBHOOK_URL}/webhook/coingate
COINGATE_SUCCESS_URL=\${WEBHOOK_URL}/coingate/success
COINGATE_CANCEL_URL=\${WEBHOOK_URL}/coingate/cancel

# Application Settings
DEBUG=False
LOG_LEVEL=INFO
MAX_PAYMENT_AMOUNT=10000
MIN_PAYMENT_AMOUNT=1
EOL
        
        echo "✅ Environment file created. Please edit .env with your actual configuration values."
        echo "⚠️  Important: Update all placeholder values in .env before continuing!"
        
        read -p "Press Enter after updating .env file to continue..."
    else
        echo "✅ Environment file already exists"
    fi
}

# Setup systemd services
setup_systemd_services() {
    echo "🔧 Setting up systemd services..."
    
    # Create bot service
    sudo tee /etc/systemd/system/telegram-bot.service > /dev/null << EOL
[Unit]
Description=Telegram Payment Bot
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL

    # Create webhook service
    sudo tee /etc/systemd/system/telegram-bot-webhook.service > /dev/null << EOL
[Unit]
Description=Telegram Payment Bot Webhook Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/python -m uvicorn webhook_server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOL

    # Reload systemd and enable services
    sudo systemctl daemon-reload
    sudo systemctl enable telegram-bot.service
    sudo systemctl enable telegram-bot-webhook.service
    
    echo "✅ Systemd services created"
}

# Setup Nginx reverse proxy
setup_nginx() {
    echo "🌐 Setting up Nginx reverse proxy..."
    
    # Get domain name
    read -p "Enter your domain name (e.g., yourdomain.com): " DOMAIN_NAME
    
    # Create Nginx configuration
    sudo tee /etc/nginx/sites-available/telegram-bot << EOL
server {
    listen 80;
    server_name $DOMAIN_NAME;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
}
EOL

    # Enable site
    sudo ln -sf /etc/nginx/sites-available/telegram-bot /etc/nginx/sites-enabled/
    sudo nginx -t
    sudo systemctl restart nginx
    sudo systemctl enable nginx
    
    echo "✅ Nginx configured"
}

# Setup SSL with Let's Encrypt
setup_ssl() {
    echo "🔒 Setting up SSL certificate..."
    
    # Get SSL certificate
    sudo certbot --nginx -d $DOMAIN_NAME --non-interactive --agree-tos --email admin@$DOMAIN_NAME
    
    # Setup auto-renewal
    sudo systemctl enable certbot.timer
    
    echo "✅ SSL certificate installed"
}

# Setup database tables
initialize_database() {
    echo "🗃️ Initializing database tables..."
    
    source venv/bin/activate
    python -c "
from database import db
from models import User, Order, Payment, SupportTicket
db.create_tables()
print('Database tables created successfully')
"
    
    echo "✅ Database initialized"
}

# Setup log rotation
setup_logging() {
    echo "📝 Setting up log rotation..."
    
    sudo tee /etc/logrotate.d/telegram-bot << EOL
$(pwd)/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $USER $USER
    postrotate
        systemctl reload telegram-bot telegram-bot-webhook
    endscript
}
EOL
    
    echo "✅ Log rotation configured"
}

# Create backup script
setup_backup() {
    echo "💾 Setting up backup system..."
    
    cat > backup.sh << 'EOL'
#!/bin/bash
# Automated backup script

BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
pg_dump $DATABASE_URL > "$BACKUP_DIR/db_backup_$DATE.sql"

# Backup receipts
tar -czf "$BACKUP_DIR/receipts_backup_$DATE.tar.gz" receipts/

# Backup logs
tar -czf "$BACKUP_DIR/logs_backup_$DATE.tar.gz" logs/

# Clean old backups (keep last 7 days)
find $BACKUP_DIR -name "*.sql" -type f -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -type f -mtime +7 -delete

echo "Backup completed: $DATE"
EOL

    chmod +x backup.sh
    
    # Add to crontab for daily backups
    (crontab -l 2>/dev/null; echo "0 2 * * * $(pwd)/backup.sh") | crontab -
    
    echo "✅ Backup system configured"
}

# Start services
start_services() {
    echo "🚀 Starting services..."
    
    sudo systemctl start telegram-bot.service
    sudo systemctl start telegram-bot-webhook.service
    
    echo "✅ Services started"
}

# Main deployment function
main() {
    echo "🚀 Telegram Payment Bot - Production Deployment"
    echo "=============================================="
    
    check_root
    setup_directories
    install_system_deps
    setup_python_env
    setup_database
    setup_redis
    setup_env_config
    setup_systemd_services
    setup_nginx
    setup_ssl
    initialize_database
    setup_logging
    setup_backup
    start_services
    
    echo ""
    echo "🎉 Deployment Complete!"
    echo "======================="
    echo ""
    echo "✅ Bot is now running in production mode"
    echo "✅ Webhook server is available at https://$DOMAIN_NAME"
    echo "✅ SSL certificate is installed and auto-renewing"
    echo "✅ Automatic backups are scheduled daily at 2 AM"
    echo ""
    echo "📋 Next Steps:"
    echo "1. Update your Telegram bot webhook URL to: https://$DOMAIN_NAME/webhook"
    echo "2. Configure PayPal and Stripe webhook URLs in their dashboards"
    echo "3. Test payments to ensure everything is working"
    echo "4. Monitor logs: sudo journalctl -u telegram-bot -f"
    echo ""
    echo "🔧 Management Commands:"
    echo "- Restart bot: sudo systemctl restart telegram-bot"
    echo "- View logs: sudo journalctl -u telegram-bot -f"
    echo "- Manual backup: ./backup.sh"
    echo "- Check status: sudo systemctl status telegram-bot telegram-bot-webhook"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
