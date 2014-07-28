#!/usr/bin/python
# -*- coding: utf-8 -*-

# Summary: Backup your facebook account
# Author: Florent Viard
# License: MIT
# Copyright (c) 2014, Florent Viard

# Run with: python facebook-dl-export.py


import logging
import httplib2
import os
from urllib import urlencode
from json import loads as js_loads
from urlparse import urljoin

CONN_DEFAULT_TIMEOUT = 30
FACEBOOK_GRAPH_ENDPOINT= "https://graph.facebook.com"

BACKUP_DEFAULT_FOLDER = 'facebook_backup'

class FbBaseException(Exception):
    pass

class FbGenericException(FbBaseException):
    pass

class FacebookConn(object):
    def __init__(self, access_token='', dev_config=None):
        self.access_token = access_token

        proxy_info = None
        if dev_config is not None:
            proxy_config = dev_config.get('proxy')
            if proxy_config is not None:
                proxy_info = httplib2.ProxyInfo(httplib2.socks.PROXY_TYPE_HTTP,
                                                proxy_config['host'],
                                                proxy_config['port'],
                                                proxy_user=proxy_config.get('login'),
                                                proxy_pass=proxy_config.get('password'))

        self.http = httplib2.Http(proxy_info=proxy_info, timeout=CONN_DEFAULT_TIMEOUT)

    def set_access_token(self, access_token):
        self.access_token = access_token

    def get_web_file(self, uri):
        file_content = None
        resp, body = self.http.request(uri, method='GET')
        if resp.status == 200 and body:
            file_content = body
        else:
            logging.warning("Error getting file: %s"% url)

        return file_content
        
    def graph_get(self, edge_path, query_params = None):
        get_result = {}

        if query_params is None:
            query_params = {}
        query_params['access_token'] = self.access_token

        uri_base = urljoin(FACEBOOK_GRAPH_ENDPOINT, edge_path)
        uri_request = uri_base + '?' + urlencode(query_params)

        resp, body = self.http.request(uri_request, method='GET')
        if resp.status == 200 and body:
            try:
                get_result = js_loads(body)
            except ValueError as exc:
                logging.exception("Error decoding graph response")
                return get_result
        elif body:
            try:
                error_info = js_loads(body)
            except ValueError as exc:
                logging.exception("Error decoding response error code")
                return get_result
            error_code = error_info.get('error', {}).get('code')
            error_subcode = error_info.get('error', {}).get('error_subcode')
            raise FbGenericException("Graph get returned error: %s (%s))"%( str(error_code), str(error_subcode)))

        return get_result

    def graph_get_all(self, edge_path, query_params = None):
        result = {}
        if query_params is None:
            query_params = {}

        result_part = self.graph_get(edge_path, query_params)
        result = result_part.get('data', {})
        while result_part:
            cursor_next = result_part.get('paging', {}).get('cursors', {}).get('after')
            if not cursor_next:
                break
            query_params['after'] = cursor_next
            result_part = self.graph_get(edge_path, query_params)
            result = result + result_part.get('data', {})

        return result
    def get_user_info(self):
        return self.graph_get("/me")

    def get_user_photos(self):
        return self.graph_get_all("/me/photos/uploaded", {'fields': 'source,created_time,updated_time,name,from,album'})

    def get_user_tagged_photos(self):
        return self.graph_get_all("/me/photos", {'fields': 'source,created_time,updated_time,name,from,album'})

    def get_user_videos(self):
        return self.graph_get_all("/me/videos/uploaded", {'fields': 'source,created_time,updated_time,name,from'})

    def get_user_tagged_videos(self):
        return self.graph_get_all("/me/videos", {'fields': 'source,created_time,updated_time,name,from'})

    def download_all(self, data, backup_subfolder=BACKUP_DEFAULT_FOLDER):
        count = 0
        total = len(data)
        logging.info("==> Starting download of %d photos", total)
        for entry in data:
            if not 'source' in entry:
                continue
            count += 1
            source = entry['source']
            dest_dir = backup_subfolder
            album_name = entry.get('album', {}).get('name')
            if album_name:
                dest_dir = os.path.join(dest_dir, album_name)
                if not os.path.exists(dest_dir):
                    try:
                        os.makedirs(dest_dir)
                    except:
                        logging.exception('Error creating folder: %s'% dest_dir)
            dest_file = os.path.join(dest_dir, os.path.basename(source))
            logging.info("Downloading photo %d/%d: %s"% (count, total, dest_file))
            image_content = self.get_web_file(source)
            if image_content:
                with open(dest_file, "w") as w_fd:
                    w_fd.write(image_content)

if __name__ == '__main__':
    """==>> Debug test script starts here <<=="""
    logging.basicConfig(format='%(levelname)s: %(message)s',
                        level=logging.DEBUG)
    logging.info("Facebook-backup hello")

    f = FacebookConn("ENTERYOURACCESSTOKENHERE")

    import pprint
    #pprint.pprint(f.graph_get('me'))
    print "===================="
    #pprint.pprint(f.graph_get('me/photos/uploaded'))
    #print "is: %s  max: %s "%( str(len(f.graph_get('me/photos/uploaded')['data'])), str(len(f.graph_get_all('me/photos/uploaded'))) )
    #pprint.pprint(f.get_user_photos())

    data = f.get_user_photos()
    if data:
        dl_dest = os.path.join(BACKUP_DEFAULT_FOLDER, 'my_photos')
        f.download_all(data, dl_dest)
    else:
        logging.info("No uploaded photo to download")
    
    data = f.get_user_tagged_photos()
    if data:
        dl_dest = os.path.join(BACKUP_DEFAULT_FOLDER, 'photos_of_me')
        f.download_all(data, dl_dest)
    else:
        logging.info("No photo of you to download")

    data = f.get_user_videos()
    if data:
        dl_dest = os.path.join(BACKUP_DEFAULT_FOLDER, 'my_videos')
        f.download_all(data, dl_dest)
    else:
        logging.info("No uploaded video to download")
    
    data = f.get_user_tagged_videos()
    if data:
        dl_dest = os.path.join(BACKUP_DEFAULT_FOLDER, 'videos_of_me')
        f.download_all(data, dl_dest)
    else:
        logging.info("No video of you to download")
