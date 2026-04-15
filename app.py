from flask import Flask, render_template
from config import Config
from models import mongo, login_manager, mail, limiter, csrf, init_indexes, init_redis
import logging
import os

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configure Logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    else:
        logging.basicConfig(level=logging.DEBUG)
    
    # Silence noisy loggers
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.INFO)

    # Initialize extensions
    mongo.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)
    
    # Initialize DB Indexes
    init_indexes(app)
    
    # Initialize Redis globally
    init_redis(app)

    # Context Processor to inject config into templates
    @app.context_processor
    def inject_config():
        return dict(config=app.config)

    # Register blueprints
    from routes.auth import auth as auth_blueprint
    from routes.main import main as main_blueprint
    from routes.voter import voter as voter_blueprint
    from routes.admin import admin as admin_blueprint
    from routes.e_epic import e_epic as e_epic_blueprint

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)
    app.register_blueprint(voter_blueprint, url_prefix='/voter')
    app.register_blueprint(admin_blueprint, url_prefix='/admin')
    app.register_blueprint(e_epic_blueprint, url_prefix='/e-epic')

    # --- BUG-015 FIX: Proper styled error handlers ---
    @app.errorhandler(400)
    def bad_request(e):
        return render_template('errors/400.html'), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return render_template('errors/413.html'), 413

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f"Server Error: {e}")
        return render_template('errors/500.html'), 500

    return app

if __name__ == '__main__':
    # Restored for backward compatibility with 'python app.py'
    app = create_app()
    # Use reloader=True to ensure code changes are picked up automatically
    app.run(debug=True, port=5000, use_reloader=True)
