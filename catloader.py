import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import GdkPixbuf
from gi.repository import Gdk
import requests
import time
import sys

class Image(object):
    def __init__(self, url, mime, raw_data):
        self.url = url
        self.mime = mime
        self.raw_data = raw_data

class CatIterator(object):
    def __init__(self, category = sys.argv[1:], allowed_mimetypes = ['image/jpeg', 'image/png']):
        self._session = requests.Session()
        self.url = "https://commons.wikimedia.org/w/api.php"
        self.allowed_mimetypes = allowed_mimetypes
        self.headers = requests.utils.default_headers()
        self.headers.update({"User-Agent" : "CatDownloader/0.1 CatDownloader/0.1" })

        if not len(category) > 0:
            self.category = "Cats"
        else:
            self.category = " ".join(category)

        self._search_params = self.__search_params(category)
       
        self._prev_images = []
        self._next_images = []
        self._images = self.__images()

    def __search_params(self, category):
        """ Parameters for finding pictures of the given category."""
        return {
                "action": "query",
                "format":  "json",
                "prop": "images",
                "imlimit": 50,
                "redirects" : 1,
                "titles": self.category
            }


    def __download_params(self, forImage):
        ''' Parameters for finding the url and mime info of the given picture.'''
        return {
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "titles": forImage,
                "iiprop": "url|mime"
            }
    
    def __find_image_names(self):
        ''' Generate the names of images in self.category. '''
        done = False
        while not done:
            cat_query = self._session.get(
                    url = self.url,
                    params = self._search_params,
                    headers = self.headers)
            cat_query = cat_query.json()        
            if not "continue" in cat_query:
                done = True
            else:
                for k in cat_query["continue"].keys():
                    self._search_params[k] = cat_query["continue"][k]
            for page in cat_query["query"]["pages"].values():
                if not "images" in page.keys():
                    done = True
                    break
                for image in page["images"]:
                    yield image["title"]
    
    def __find_url_and_mime(self, image_name):
        ''' Return the url and mime info of the image with the given name. '''
        cat_query = self._session.get(
                url = self.url,
                params=self.__download_params(image_name),
                headers=self.headers)
        for page in cat_query.json()["query"]["pages"].values():
            for info in page["imageinfo"]:
                return (info["url"], info["mime"])

    def __raw_data(self, image_url):    
        reply = self._session.get(image_url, headers=self.headers)
        return reply.content


    def __images(self):
        ''' Generate all the images of self.category. '''
        image_names = self.__find_image_names()
        for name in image_names:
            (url, mime) = self.__find_url_and_mime(name)
            if mime in self.allowed_mimetypes:
                yield Image(url, mime, self.__raw_data(url))

    def __iter__(self):
        return self

    def __bool__(self):
        ''' Check if there is another picture to load. '''
        if not self._next_images:
            try:
                self._next_images.append(next(self._images))
            except StopIteration:
                return False
        return True

    def has_previous(self):
        ''' Check if there are previous elements to return. '''
        return len(self._prev_images) > 1


    def __next__(self):
        ''' Return the next image from self.category.'''
        if not self:
            raise StopIteration

        self._prev_images.append(self._next_images.pop())
        if self._prev_images:
            return self._prev_images[-1]
        else:
            raise StopIteraton
    
    def remove_current(self):
        ''' Remove the current image from the results.'''
        if self._prev_images:
            self._prev_images.pop()

    def __prev__(self):
        ''' Return the previous image from self.category.'''
        if not self.has_previous():
            raise StopIteration

        self._next_images.append(self._prev_images.pop())
        return self._prev_images[-1]

class CatLoader(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)
        self.connect("destroy", Gtk.main_quit)

        self.images = CatIterator()

        # Insert navigation bar at the top
        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        hb.props.title = "Here are pictures of {}:".format(self.images.category)
        self.set_titlebar(hb)
    
        # Box with buttons for navigation
        box = Gtk.Box()
        hb.pack_start(box)
        Gtk.StyleContext.add_class(box.get_style_context(), "linked")

        # Insert back button
        self._back_button = Gtk.Button()
        self._back_button.add(Gtk.Arrow(arrow_type = Gtk.ArrowType.LEFT, shadow_type = Gtk.ShadowType.NONE))
        self._back_button.connect("clicked", self._prev_image)
        box.add(self._back_button)
       
        # Insert forward button
        self._forward_button = Gtk.Button()
        self._forward_button.add(Gtk.Arrow(arrow_type = Gtk.ArrowType.RIGHT, shadow_type = Gtk.ShadowType.NONE))
        self._forward_button.connect("clicked", self._next_image)
        box.add(self._forward_button)

        # Insert the image
        self.image = Gtk.Image()
        self.image_box = Gtk.EventBox()
        self.image_box.add(self.image)
        self.image_box.connect("button-press-event", self.click_image)
        # self.connect("check-resize", self._resize)
        self.add(self.image_box)

        if self.images:
            self._next_image(self._forward_button)
        else:
            label = Gtk.Label(label = "Sorry, no images found!")
            self.remove(self.image_box)
            self.add(label)
            self._back_button.set_sensitive(False)
            self._forward_button.set_sensitive(False)

        self.set_default_size(720, 480)
        self.show_all()

    def click_image(self, image_box, button):
        Gtk.show_uri_on_window(self, self._current_image.url, Gdk.CURRENT_TIME)

    
    #def _resize(self, container):
    #    self._load_image(self._current_image)
    #    self.set_size_request(720, 480)

    def _load_image(self, image):
        loader = GdkPixbuf.PixbufLoader.new_with_mime_type(image.mime)
        try:
            loader.write(image.raw_data)
            pixbuf = loader.get_pixbuf()
            loader.close()
        except Exception as ex:
            loader.close()
            return False
        #(wn, hn) = self.get_size()
        (wm, hm) = (720, 480) #(max(720, wn), max(480, hn))
        (wi, hi) = (pixbuf.get_width(), pixbuf.get_height())
        (w, h) = (wm, wm * hi // wi) if wi > hi else (hm * wi // hi, hm)
        pixbuf = pixbuf.scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR)
        self.image.set_from_pixbuf(pixbuf)
        self._current_image = image
        #self.image_box.
        return True

    def _next_image(self, forward_button):
        if self.images:
            next_image = next(self.images)
            if not self._load_image(next_image):
                self.images.remove_image(next_image)
                self._next_image(self._forward_button)
                return
        forward_button.set_sensitive(bool(self.images))
        self._back_button.set_sensitive(self.images.has_previous())

    def _prev_image(self, backward_button):
        if self.images.has_previous():
            prev_image = self.images.__prev__()
            if not self._load_image(prev_image):
                self.images.remove_image(prev_image)
                self._prev_image(backward_button)
                return
        backward_button.set_sensitive(self.images.has_previous())
        self._forward_button.set_sensitive(bool(self.images))

if __name__ == "__main__":
    cl = CatLoader()
    Gtk.main()
