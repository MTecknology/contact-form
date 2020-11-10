#!/usr/bin/python
'''
A basic bottle app skeleton
'''

import bottle
import ConfigParser
import email
import hashlib
import redis
import random
import string
import socket

from email.mime.text import MIMEText
from subprocess import Popen, PIPE

# Read configuration
conf = ConfigParser.SafeConfigParser({
    'send_to': '',
    'cache_host': 'localhost',
    'cache_db': '0',
    'cache_ttl': '3600'})
conf.read('settings.cfg')

# App stuff
app = application = bottle.Bottle()
cache = redis.Redis(host=conf.get('bottle', 'cache_host'), db=int(conf.get('bottle', 'cache_db')))

@app.get('/')
@app.get('/contact')
@app.get('/contact/')
def view_form():
    ''' Return the themed search form. '''
    key = hashlib.sha256(bottle.request.environ.get('REMOTE_ADDR')).hexdigest()
    if cache.exists(key):
        value = cache.get(key)
    else:
        value = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(46))
        cache.set(key, value)
        cache.expire(key, int(conf.get('bottle', 'cache_ttl')))

    return bottle.jinja2_template('contact_form.html', secret=value)


@app.post('/')
@app.post('/contact')
@app.post('/contact/')
def check_form():
    '''
    Processes the form.
    '''
    key = hashlib.sha256(bottle.request.environ.get('REMOTE_ADDR')).hexdigest()
    pd = {
        'name': bottle.request.POST.get('name', '').strip(),
        'secret': bottle.request.POST.get('lead', '').strip(),
        'email': bottle.request.POST.get('email', '').strip(),
        'phone': bottle.request.POST.get('phone', '').strip(),
        'code': bottle.request.POST.get('code', '').strip()}

    if not cache.exists(key):
        return bottle.jinja2_template('msg.html', code=200, title='oops...', message='Your post triggered my spam filter. (code=787)')
    elif int(cache.ttl(key)) > int(conf.get('bottle', 'cache_ttl')) - 30:
        return bottle.jinja2_template('msg.html', code=200, title='oops...', message='Your post triggered my spam filter. (code=383)')

    cs = cache.get(key)
    if cs == 'BLOCK':
        return bottle.jinja2_template('msg.html', code=200, title='oops...', message='Your post triggered my spam filter. (code=429)')
    elif cs != pd['secret']:
        return bottle.jinja2_template('msg.html', code=200, title='oops...', message='Your post triggered my spam filter. (code=581)')
    elif pd['phone'] != '':
        return bottle.jinja2_template('msg.html', code=200, title='oops...', message='Your post triggered my spam filter. (code=814)')

    fromaddr = 'noreply@{}'.format(socket.getfqdn())
    message = MIMEText('Name: {}\nEmail: {}\nMessage:\n{}'.format(
        pd['name'],
        pd['email'],
        pd['code']))
    message['From'] = fromaddr
    message['To'] = conf.get('bottle', 'send_to')
    message['Subject'] = 'Contact Form'

    p = Popen(["/usr/sbin/sendmail", "-t", "-oi"], stdin=PIPE)
    p.communicate(message.as_string())

    # Set a one minute delay before allowing another sumbission
    cache.set(key, 'BLOCK')
    cache.expire(key, 60)

    return bottle.jinja2_template('msg.html', code=200, title='Message Sent', message='Thanks for your message! :)')


class StripPathMiddleware(object):
    '''
    Get that slash out of the request
    '''
    def __init__(self, a):
        self.a = a
    def __call__(self, e, h):
        e['PATH_INFO'] = e['PATH_INFO'].rstrip('/')
        return self.a(e, h)


if __name__ == '__main__':
    bottle.run(app=StripPathMiddleware(app),
        host='0.0.0.0',
        port=8080)
