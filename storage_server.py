import logging
import BaseHTTPServer
import sqlite3
import xml.dom.minidom as minidom

import other.utils as utils

logger_output_to_console = True
logger_output_to_file = True
logger_name = "StorageServer"
logger_filename = "storage_server.log"
logger = utils.create_logger(logger_name, logger_filename, -1, logger_output_to_console, logger_output_to_file)

address = ("127.0.0.1", 8000)

class StorageServer(object):
    def start(self):
        httpd = StorageHTTPServer((address[0], address[1]), StorageHTTPServerHandler)
        logger.log(logging.INFO, "Now listening for connections on %s:%d...", address[0], address[1])
        httpd.serve_forever()

class StorageHTTPServer(BaseHTTPServer.HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)
        
        self.db = sqlite3.connect('storage.db')
        self.tables = {}
        
        cursor = self.db.cursor()
        
        if not self.table_exists('typedata'):
            cursor.execute('CREATE TABLE typedata (tbl TEXT, col TEXT, type TEXT)')
        if not self.table_exists('g2649_bbdx_player'):
            cursor.execute('CREATE TABLE g2649_bbdx_player (recordid INT, stat INT)')
            cursor.execute('INSERT INTO typedata VALUES ("g2649_bbdx_player", "recordid", "intValue"), ("g2649_bbdx_player", "stat", "intValue")')
        
        # load column info into memory, unfortunately there's no simple way
        # to check for column-existence so get that data in advance
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabledata = cursor.fetchall()
        for t in tabledata:
            cursor.execute("PRAGMA table_info(%s)" % t[0]) # yeah I know but parameters don't work in pragmas, and inserting table names like that should be safe
            columns = cursor.fetchall()
            columndata = []
            for c in columns:
                columndata.append(c[1])
            self.tables[t[0]] = columndata
        
        self.db.commit()
        
    def table_exists(self, name):
        cursor = self.db.cursor()
        cursor.execute("SELECT Count(1) FROM sqlite_master WHERE type='table' AND name=?", (name,))
        exists = cursor.fetchone()[0]
        return True if exists else False
    
class StorageHTTPServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_POST(self):
        # Alright, in case anyone is wondering: Yes, I am faking a SOAP service
        # instead of using an actual one. That's because I've tried to do this
        # with several actual python SOAP services and none of them give me the
        # ability to return the exact format that I want.
        # (Or make any kind of sense in case of ZSI...)
        
        if self.path == "/SakeStorageServer/StorageServer.asmx":
            length = int(self.headers['content-length'])
            action = self.headers['SOAPAction']
            post = self.rfile.read(length)
            logger.log(logging.DEBUG, "SakeStorageServer SOAPAction %s", action)
            
            ret = '<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema"><soap:Body>'
            
            if action == '"http://gamespy.net/sake/SearchForRecords"':
                dom = minidom.parseString(post)
                data = dom.getElementsByTagName('SOAP-ENV:Body')[0].getElementsByTagName('ns1:SearchForRecords')[0]
                gameid = str(int(data.getElementsByTagName('ns1:gameid')[0].firstChild.data))
                tableid = data.getElementsByTagName('ns1:tableid')[0].firstChild.data
                
                table = 'g' + gameid + '_' + tableid
                
                if not self.server.table_exists(table):
                    logger.log(logging.WARNING, "Unknown table access '%s' in SearchForRecords by %s", (table, self.client_address))
                    return
                
                columndata = data.getElementsByTagName('ns1:fields')[0].getElementsByTagName('ns1:string')
                
                for c in columndata:
                    if not c.firstChild.data in self.server.tables[table]:
                        logger.log(logging.WARNING, "Unknown column access '%s' in table '%s' in SearchForRecords by %s", (c.firstChild.data, table, self.client_address))
                        return
                
                
                
            elif action == '"http://gamespy.net/sake/GetRecordCount"':
                pass
            
            ret += '</soap:Body></soap:Envelope>'
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/xml; charset=utf-8')
            self.end_headers()
            
            logger.log(logging.DEBUG, "%s response to %s", (action, self.client_address))
            self.wfile.write(ret)
            

if __name__ == "__main__":
    storage_server = StorageServer()
    storage_server.start()