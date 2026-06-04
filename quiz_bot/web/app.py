from aiohttp import web
import jinja2
import aiohttp_jinja2
import os

routes = web.RouteTableDef()

@routes.get('/')
@aiohttp_jinja2.template('index.html')
async def index(request):
    return {}

def setup_app():
    app = web.Application()

    # Setup Jinja2 templates
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(template_dir))

    app.add_routes(routes)
    return app
