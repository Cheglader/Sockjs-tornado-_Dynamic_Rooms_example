'''
A short example for creating a sockjs-tornado node with dynamic channels.
Please refer to https://github.com/mrjoes/sockjs-tornado.
Author: Luis San Pablo
'''
import json
from sockjs.tornado import conn, session, SockJSConnection
from sockjs.tornado.transports import base
from sockjs.tornado.router import SockJSRouter
import tornado.ioloop
import tornado.web
import magic_api_package
          
class DynamicConnection(SockJSConnection):

    def on_open(self, request):
        self.connected.add(self)
        
    def on_message(self, message):
        ''' This method processes a message from the game client '''
        self.broadcast(self, self.connected, message):
        return
            
    def on_close(self):
        self.connected.remove(self)
        super().on_close()

class ChannelFactory(object):
    _channels = dict()
        
    def __call__(self, channel_name):
        """ This method is the dynamic channel creator. Each channel starts off with an empty
        connected set of connected sessions and a unique chnnel name.
        Args:
            request (ConnectionInfo): object which contains caller IP address, query string
            parameters and cookies associated with this request (if any).

        Returns:
            Channel if successful, None otherwise
        """
        if channel_name not in self._channels and magic_api_package.is_a_valid_name(channel_name):
            class Channel(DynamicConnection):
                connected = set()
                name = channel_name
            self._channels[channel_name] = Channel
            return Channel
        elif channel_name in self._channels:
            return self._channels[channel_name]
        else:
            return None

class ChannelSession(session.BaseSession):
    def __init__(self, conn, server, base, name):
        super(ChannelSession, self).__init__(conn, server)

        self.base = base
        self.name = name
    def send_message(self, msg, stats=True, binary=False):
        self.base.send(msg)
        
    def on_message(self, msg):
        self.conn.on_message(msg)

    def close(self, code=3000, message='Go away!'):
        self.base.send(json.dumps({"channel": self.name, "action": 'UNS'}))
        self._close(code, message)

    def _close(self, code=3000, message='Go away!'):
        """ This method is 
        Args:
            request (ConnectionInfo): object which contains caller IP address, query string
            parameters and cookies associated with this request (if any).

        Returns:
            None
        """
        super(ChannelSession, self).close(code, message)


class DummyHandler(base.BaseTransportMixin):
    """ The transport handler that will be used for sessions
    created in our multiplex connection.
    """
    name = 'multiplex_handler'

    def __init__(self, conn_info):
        self.conn_info = conn_info

    def get_conn_info(self):
        return self.conn_info


class MultiplexConnection(conn.SockJSConnection):
    channels = {}
    _channel_factory = ChannelFactory()
    def on_open(self, request):
        """ This method is called whenever the connection with the client is opened.
        Args:
            request (ConnectionInfo): object which contains caller IP address, query string
            parameters and cookies associated with this request (if any).

        Returns:
            None
        """

        self.endpoints = dict()
        self.handler = DummyHandler(request)

    def on_message(self, msg):
        """ This method is called whenever a client sends a message, which is recieved by a MultiplexConnection as an entrypoint.
        
        Args:
            msg (str): A string that should be in JSON syntax. It must contains the following keys::
            msg = {
                "channel": "The name of the Dyanmic Chanel(DynamicConnection) to be addressed."
                "action": "One of : UNS, MSG, or JOIN in this example."
                "data": "The data that will be transmitted to the channel"
            }
        Returns:
            None
        """
        message_json_object = json.loads(msg)
        '''# This creates the channel if it is not already created.
        '''
        if message_json_object['channel'] not in self.channels:
            self.channels[message_json_object['channel']] = self._channel_factory(message_json_object['channel'])
            if self.channels[message_json_object['channel']] is None:
                self.channels.pop(message_json_object['channel'])
                self.close()
        '''# Here the channel session is added to the client's endpoints if it isn't already,
        and the message is handled.
        '''
        if message_json_object['channel'] in self.endpoints:
            session = self.endpoints[message_json_object['channel']]

            if message_json_object["action"] == 'UNS':
                del self.endpoints[message_json_object['channel']]
                session._close()
            elif message_json_object["action"] == 'MSG':
                session.on_message(message_json_object["data"])
        else:
            if message_json_object["action"] == 'JOIN':
                session = ChannelSession(self.channels[message_json_object['channel']],
                                        self.session.server,
                                        self,
                                        message_json_object['channel'])
                '''# Pass the handler to the newly created session. This
                enables the channel to use the request information provided by the handler
                such as the request cookies.
                '''
                session.set_handler(self.handler)
                session.verify_state()

                self.endpoints[message_json_object['channel']] = session

    def on_close(self):
        """ This method is called when the connection with the client is closed, and
        so we must close the channel endpoint sessions that the client may have created.

        Returns:
            None
        """
        for chan in self.endpoints:
            self.endpoints[chan]._close()
        
    @classmethod
    def get(cls, listening_thread,  **kwargs):
        return type('MultiplexRouter', (MultiplexConnection,), dict(channels=kwargs))
    
class IndexHandler(tornado.web.RequestHandler):
    """# Regular HTTP handler to serve an error page
    """
    def get(self):
        self.render('index.html')

if __name__ == "__main__":
    #Create multiplexer
    connection_router = MultiplexConnection.get()

    # Register multiplexer
    EchoRouter = SockJSRouter(connection_router, '/sampleapp/echo')
    
    # Create application
    app = tornado.web.Application([(r'/sampleapp/', IndexHandler)]  + EchoRouter.urls)
    app.listen(9969, address='127.0.0.1')

    tornado.ioloop.IOLoop.instance().start()
    
    
    
    
    
    
    