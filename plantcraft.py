from __future__ import division

import sys
import math
import random
import time

from collections import deque
from pyglet import image
from pyglet.gl import *
from pyglet.graphics import TextureGroup
from pyglet.window import key, mouse

TICKS_PER_SEC = 60

# Size of sectors used to ease block loading.
#SECTOR_SIZE = 16

SPEED = 15

INIT_ENERGY = 500
ENERGY = INIT_ENERGY
ROOT_COST = 10
ENERGY_REWARD = 100

DEGREES= u'\N{DEGREE SIGN}'
DIRECTIONS = (key.N, key.S, key.W, key.E, key.U, key.D)
NUM_KEYS = (key._1, key._2, key._3, key._4, key._5, key._6, key._7, key._8, key._9, key._0)

TEXTURE_PATH = "roots.png"

if sys.version_info[0] >= 3:
    xrange = range

def cube_vertices(x, y, z, n):
    """ Return the vertices of the cube at position x, y, z with size 2*n.

    """
    return [
        x-n,y+n,z-n, x-n,y+n,z+n, x+n,y+n,z+n, x+n,y+n,z-n,  # top
        x-n,y-n,z-n, x+n,y-n,z-n, x+n,y-n,z+n, x-n,y-n,z+n,  # bottom
        x-n,y-n,z-n, x-n,y-n,z+n, x-n,y+n,z+n, x-n,y+n,z-n,  # left
        x+n,y-n,z+n, x+n,y-n,z-n, x+n,y+n,z-n, x+n,y+n,z+n,  # right
        x-n,y-n,z+n, x+n,y-n,z+n, x+n,y+n,z+n, x-n,y+n,z+n,  # front
        x+n,y-n,z-n, x-n,y-n,z-n, x-n,y+n,z-n, x+n,y+n,z-n,  # back
    ]


def calcTextureCoords(which, n=8):
    m = 1.0 / n
    left = which*m
    right = left+m - 0.001
    left += 0.001
    return 6*[left, 0, right, 0, right, 1, left, 1]

TEXTURES = (calcTextureCoords(1), calcTextureCoords(2), calcTextureCoords(3), calcTextureCoords(4), calcTextureCoords(5))
#TEXTURES = (calcTextureCoords(1), calcTextureCoords(0), calcTextureCoords(0), calcTextureCoords(0))
STALK_TEXTURE = calcTextureCoords(0)
#TEXTURE_COLORS = (None, (255,128,128,255), (128,255,153,255), (128,153,255,255))
TEXTURE_COLORS = (None, (128,255,255,255), (128,180,255,255), (204, 128, 255, 255))
ACTION_TEXT = "Adding to root tip "

FACES = [( 0, 1, 0), ( 0,-1, 0), (-1, 0, 0), ( 1, 0, 0), ( 0, 0, 1), ( 0, 0,-1),]


class RootSystem(object):

    def __init__(self):

        # A Batch is a collection of vertex lists for batched rendering.
        self.batch = pyglet.graphics.Batch()

        # A TextureGroup manages an OpenGL texture.
        self.group = TextureGroup(image.load(TEXTURE_PATH).get_texture())

        # A mapping from position to the texture of the block at that position.
        # This defines all the blocks that are currently in the world.
        self.world = {}

        # Same mapping as `world` but only contains blocks that are shown.
        self.shown = {}

        # Mapping from position to a pyglet `VertextList` for all shown blocks.
        self._shown = {}

        # Mapping from sector to a list of positions inside that sector.
        #self.sectors = {}

        # Simple function queue implementation. The queue is populated with
        # _show_block() and _hide_block() calls
        self.queue = deque()

        self._initialize()


    def _initialize(self):
        """ Initialize the world by placing all the blocks.

        """
        #n = 80  # 1/2 width and height of world
        #s = 1  # step size
        #y = 0  # initial y height

        self.tipPositions = [None, (-1,0,0), (1,0,0), (0,-1,0)]
        for i in range(1,len(self.tipPositions)):
            self.add_block(self.tipPositions[i], TEXTURES[i])

        self.add_block((0,0,0), TEXTURES[0])
        for i in range(1,60):
            self.add_block((0,i,0), STALK_TEXTURE)

        for i in range(1,100):
            self.add_block((random.randint(-20,20), random.randint(-20,0),random.randint(-20,20)), TEXTURES[4])

    def addToTip(self, whichTip, direction):
        global ENERGY #KLUDGE. Replace with good design later
        if (ENERGY <= ROOT_COST): return False
        oldTip = self.tipPositions[whichTip]
        newTip = RootSystem.modByDirection(oldTip, direction)

        # don't accept new positions that collide or are above ground
        #print(newTip)
        #if newTip in self.world:
        #    print(self.world[newTip]==TEXTURES[4])
        #    print(newTip in self.world)
        #    print(newTip in self.world and self.world[newTip] == TEXTURES[4])
        if newTip in self.world:
            if self.world[newTip] == TEXTURES[4]:
                ENERGY+=ENERGY_REWARD
            else: return False
        #if newTip in self.world: return False
        if newTip[1] > 0: return False
        ENERGY -= ROOT_COST

        self.uncolorBlock(oldTip)
        
        self.add_block(newTip, TEXTURES[whichTip])
        self.tipPositions[whichTip] = newTip
            #print(str(oldTip) +" -> " + str(newTip))
        return True

    @staticmethod
    def modByDirection(start, direc):
        if direc==key.N or direc=='n' or direc=='N': return (start[0], start[1], start[2]-1)
        if direc==key.S or direc=='s' or direc=='S': return (start[0], start[1], start[2]+1)
        if direc==key.E or direc=='e' or direc=='E': return (start[0]+1, start[1], start[2])
        if direc==key.W or direc=='w' or direc=='W': return (start[0]-1, start[1], start[2])
        if direc==key.U or direc=='u' or direc=='U': return (start[0], start[1]+1, start[2])
        if direc==key.D or direc=='d' or direc=='D': return (start[0], start[1]-1, start[2])
        return start

    def exposed(self, position):
        """ Returns False is given `position` is surrounded on all 6 sides by
        blocks, True otherwise.

        """
        x, y, z = position
        for dx, dy, dz in FACES:
            if (x + dx, y + dy, z + dz) not in self.world:
                return True
        return False

    def add_block(self, position, texture, immediate=True):
        """ Add a block with the given `texture` and `position` to the world.

        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to add.
        texture : list of len 3
            The coordinates of the texture squares. Use `tex_coords()` to
            generate.
        immediate : bool
            Whether or not to draw the block immediately.

        """
        if position in self.world:
            self.remove_block(position, immediate)
        self.world[position] = texture
        #self.sectors.setdefault(sectorize(position), []).append(position)
        if immediate:
            if self.exposed(position):
                self.show_block(position)
            self.check_neighbors(position)

    def uncolorBlock(self, position, immediate=True):
        if position not in self.world: return

        self.world[position] = TEXTURES[0]
        if self.exposed(position):
            #print(self.world[position], TEXTURES[0])

            self.shown[position] = TEXTURES[0]
            if immediate:
                self.hide_block(position)
                self.show_block(position)
            
    def remove_block(self, position, immediate=True):
        """ Remove the block at the given `position`.

        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to remove.
        immediate : bool
            Whether or not to immediately remove block from canvas.

        """
        del self.world[position]
        #self.sectors[sectorize(position)].remove(position)
        if immediate:
            if position in self.shown:
                self.hide_block(position)
            self.check_neighbors(position)

    def check_neighbors(self, position):
        """ Check all blocks surrounding `position` and ensure their visual
        state is current. This means hiding blocks that are not exposed and
        ensuring that all exposed blocks are shown. Usually used after a block
        is added or removed.

        """
        x, y, z = position
        for dx, dy, dz in FACES:
            key = (x + dx, y + dy, z + dz)
            if key not in self.world:
                continue
            if self.exposed(key):
                if key not in self.shown:
                    self.show_block(key)
            else:
                if key in self.shown:
                    self.hide_block(key)

    def show_block(self, position, immediate=True):
        """ Show the block at the given `position`. This method assumes the
        block has already been added with add_block()

        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to show.
        immediate : bool
            Whether or not to show the block immediately.

        """
        texture = self.world[position]
        self.shown[position] = texture
        if immediate:
            self._show_block(position, texture)
        else:
            self._enqueue(self._show_block, position, texture)

    def _show_block(self, position, texture):
        """ Private implementation of the `show_block()` method.

        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to show.
        texture : list of len 3
            The coordinates of the texture squares. Use `tex_coords()` to
            generate.

        """
        x, y, z = position
        vertex_data = cube_vertices(x, y, z, 0.5)
        texture_data = list(texture)
        # create vertex list
        # FIXME Maybe `add_indexed()` should be used instead
        self._shown[position] = self.batch.add(24, GL_QUADS, self.group, ('v3f/static', vertex_data), ('t2f/static', texture_data))

    def hide_block(self, position, immediate=True):
        """ Hide the block at the given `position`. Hiding does not remove the
        block from the world.

        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to hide.
        immediate : bool
            Whether or not to immediately remove the block from the canvas.

        """
        self.shown.pop(position)
        if immediate:
            self._hide_block(position)
        else:
            self._enqueue(self._hide_block, position)

    def _hide_block(self, position):
        """ Private implementation of the 'hide_block()` method.

        """
        self._shown.pop(position).delete()

    def _enqueue(self, func, *args):
        """ Add `func` to the internal queue.

        """
        self.queue.append((func, args))

    def _dequeue(self):
        """ Pop the top function from the internal queue and call it.

        """
        func, args = self.queue.popleft()
        func(*args)

    def process_queue(self):
        """ Process the entire queue while taking periodic breaks. This allows
        the game loop to run smoothly. The queue contains calls to
        _show_block() and _hide_block() so this method should be called if
        add_block() or remove_block() was called with immediate=False

        """
        start = time.clock()
        while self.queue and time.clock() - start < 1.0 / TICKS_PER_SEC:
            self._dequeue()

    def process_entire_queue(self):
        """ Process the entire queue with no breaks.

        """
        while self.queue:
            self._dequeue()


class Window(pyglet.window.Window):

    def __init__(self, *args, **kwargs):
        super(Window, self).__init__(*args, **kwargs)

        # Whether or not the window exclusively captures the mouse.
        self.exclusive = False

        # Strafing is moving lateral to the direction you are facing,
        # e.g. moving to the left or right while continuing to face forward.
        #
        # First element is -1 when moving forward, 1 when moving back, and 0
        # otherwise. The second element is -1 when moving left, 1 when moving
        # right, and 0 otherwise.
        self.motion = [0, 0, 0]

        # Current (x, y, z) position in the world, specified with floats. Note
        # that, perhaps unlike in math class, the y-axis is the vertical axis.
        self.position = (0, 0, 10)
        #self.spherical = (0, 0, 10)

        # First element is rotation of the player in the x-z plane (ground
        # plane) measured from the z-axis down. The second is the rotation
        # angle from the ground plane up. Rotation is in degrees.
        #
        # The vertical plane rotation ranges from -90 (looking straight down) to
        # 90 (looking straight up). The horizontal rotation range is unbounded.
        self.rotation = (0, 0)

        # Which sector the player is currently in.
        #self.sector = None

        # Velocity in the y (upward) direction.
        self.dy = 0

        # A list of blocks the player can place. Hit num keys to cycle.
        #self.inventory = [TIP2, BAREROOT, TIP1]

        # The current block the user can place. Hit num keys to cycle.
        #self.block = self.inventory[0]

        self.currentTip = 1

        # Instance of the model that handles the world.
        self.rootSystem = RootSystem()

        self.positionLabel = pyglet.text.Label('', font_name="Arial", font_size=18, x=self.width/2, 
                                        anchor_x='center', y=self.height-10, anchor_y='top', 
                                        color=(255,255,255,255))

        self.actionLabel = pyglet.text.Label(ACTION_TEXT+"1", font_name="Arial", font_size=18, x=self.width/2, 
                                             anchor_x="center", y=10, anchor_y="bottom", color=TEXTURE_COLORS[1])

        self.controlsLabel = pyglet.text.Label(ACTION_TEXT+"1", font_name="Arial", font_size=18, x=self.width/4, 
                                             anchor_x="center", y=10, anchor_y="bottom", color=(255,255,255,255))
        self.controlsLabel.text = "nsewud"

        self.energyLabel = pyglet.text.Label(ACTION_TEXT+"1", font_name="Arial", font_size=18, x=self.width/5, 
                                             anchor_x="center", y=self.height-10, anchor_y="top", color=(255,0,0,255))

        # This call schedules the `update()` method to be called
        # TICKS_PER_SEC. This is the main game event loop.
        pyglet.clock.schedule_interval(self.update, 1.0 / TICKS_PER_SEC)

    def set_exclusive_mouse(self, exclusive):
        """ If `exclusive` is True, the game will capture the mouse, if False
        the game will ignore the mouse.

        """
        super(Window, self).set_exclusive_mouse(exclusive)
        self.exclusive = exclusive

    def get_sight_vector(self):
        """ Returns the current line of sight vector indicating the direction
        the player is looking.

        """
        x, y = self.rotation
        # y ranges from -90 to 90, or -pi/2 to pi/2, so m ranges from 0 to 1 and
        # is 1 when looking ahead parallel to the ground and 0 when looking
        # straight up or down.
        m = math.cos(math.radians(y))
        # dy ranges from -1 to 1 and is -1 when looking straight down and 1 when
        # looking straight up.
        dy = math.sin(math.radians(y))
        dx = math.cos(math.radians(x - 90)) * m
        dz = math.sin(math.radians(x - 90)) * m
        return (dx, dy, dz)

    def update(self, dt):
        """ This method is scheduled to be called repeatedly by the pyglet
        clock.

        Parameters
        ----------
        dt : float
            The change in time since the last call.

        """
        #self.rootSystem.process_queue()
        self.rootSystem.process_entire_queue()
        m = 8
        dt = min(dt, 0.2)
        for _ in xrange(m):
            self._update(dt / m)

    def _update(self, dt):
        """ Private implementation of the `update()` method. This is where most
        of the motion logic lives, along with gravity and collision detection.

        Parameters
        ----------
        dt : float
            The change in time since the last call.

        """
        speed = SPEED
        d = dt * speed # distance covered this tick.
        #dx, dy, dz = self.get_motion_vector()
        x, y, z = self.position
        dx, dy, dz = [a * d for a in self.motion]
        theta = math.radians(self.rotation[0])
        x += dx*math.cos(theta) + -dz*math.sin(theta)
        y += dy
        z += dx*math.sin(theta) + dz*math.cos(theta)
        self.position = (x, y, z)

        # speed up smaller circles--but not too fast
        #speedup = min(0.5, 1 / math.cos(math.radians(p)) / r)

        #t += (180 * dt / math.pi * speedup)
        #while t >= 360: t -= 360
        #while t < 0: t += 360 
        #p += (180 * dp / math.pi / r)
        #if p > 90: p = 90
        #if p < -90: p = -90
        #r += dr
        #if r < 1: r = 1

        

#    def on_mouse_press(self, x, y, button, modifiers):
#        """ Called when a mouse button is pressed. See pyglet docs for button
#        amd modifier mappings.
#
#        Parameters
#        ----------
#        x, y : int
#            The coordinates of the mouse click. Always center of the screen if
#            the mouse is captured.
#        button : int
#            Number representing mouse button that was clicked. 1 = left button,
#            4 = right button.
#        modifiers : int
#            Number representing any modifying keys that were pressed when the
#            mouse button was clicked.
#
#        """
#        if self.exclusive:
#            vector = self.get_sight_vector()
#            block, previous = self.rootSystem.hit_test(self.position, vector)
#            if (button == mouse.RIGHT) or \
#                    ((button == mouse.LEFT) and (modifiers & key.MOD_CTRL)):
#                # ON OSX, control + left click = right click.
#                if previous:
#                    self.rootSystem.add_block(previous, self.block)
#            elif button == pyglet.window.mouse.LEFT and block:
#                texture = self.rootSystem.world[block]
#                if texture != TIP3:
#                    self.rootSystem.remove_block(block)
#        else:
#            self.set_exclusive_mouse(True)

    def on_mouse_motion(self, x, y, dx, dy):
        """ Called when the player moves the mouse.

        Parameters
        ----------
        x, y : int
            The coordinates of the mouse click. Always center of the screen if
            the mouse is captured.
        dx, dy : float
            The movement of the mouse.

        """
        if self.exclusive:
            m = 0.15
            x, y = self.rotation
            x, y = x + dx * m, y + dy * m
            y = max(-90, min(90, y))
            self.rotation = (x, y)

    def on_key_press(self, symbol, modifiers):
        """ Called when the player presses a key. See pyglet docs for key
        mappings.

        Parameters
        ----------
        symbol : int
            Number representing the key that was pressed.
        modifiers : int
            Number representing any modifying keys that were pressed.

        """

        if symbol == key.LEFT or symbol== key.A:
            self.motion[0] -= 1
        elif symbol == key.RIGHT or symbol == key.D:
            self.motion[0] += 1
        elif symbol == key.SPACE:
            self.motion[1] += 1
        elif symbol == key.LSHIFT:
            self.motion[1] -= 1
        elif symbol == key.UP or symbol == key.W:
            self.motion[2] -= 1
        elif symbol == key.DOWN or symbol == key.S:
            self.motion[2] += 1
        elif symbol == key.ESCAPE:
            self.set_exclusive_mouse(False)
        elif symbol in NUM_KEYS:
            self.currentTip = (symbol - NUM_KEYS[0]) % (len(TEXTURES) - 1) + 1
            self.actionLabel.text = ACTION_TEXT + str(self.currentTip)
            self.actionLabel.color = TEXTURE_COLORS[self.currentTip]
            #self.block = self.inventory[index]
        elif symbol in DIRECTIONS:
            self.rootSystem.addToTip(self.currentTip, symbol)

    def on_key_release(self, symbol, modifiers):
        """ Called when the player releases a key. See pyglet docs for key
        mappings.

        Parameters
        ----------
        symbol : int
            Number representing the key that was pressed.
        modifiers : int
            Number representing any modifying keys that were pressed.

        """
        if symbol == key.LEFT or symbol== key.A:
            self.motion[0] += 1
        elif symbol == key.RIGHT or symbol == key.D:
            self.motion[0] -= 1
        elif symbol == key.SPACE:
            self.motion[1] -= 1
        elif symbol == key.LSHIFT:
            self.motion[1] += 1
        elif symbol == key.UP or symbol == key.W:
            self.motion[2] += 1
        elif symbol == key.DOWN or symbol == key.S:
            self.motion[2] -= 1

    def on_resize(self, width, height):
        """ Called when the window is resized to a new `width` and `height`.

        """
        # adjust labels
        self.positionLabel.x = self.actionLabel.x = width/2
        self.positionLabel.y = height-10

    def set_2d(self):
        """ Configure OpenGL to draw in 2d.

        """
        width, height = self.get_size()
        glDisable(GL_DEPTH_TEST)
        viewport = self.get_viewport_size()
        glViewport(0, 0, max(1, viewport[0]), max(1, viewport[1]))
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, max(1, width), 0, max(1, height), -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def set_3d(self):
        """ Configure OpenGL to draw in 3d.

        """
        width, height = self.get_size()
        glEnable(GL_DEPTH_TEST)
        viewport = self.get_viewport_size()
        glViewport(0, 0, max(1, viewport[0]), max(1, viewport[1]))
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(65.0, width / float(height), 0.1, 60.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # remember OpenGL is backwards!
        x, y = self.rotation
        glRotatef(x, 0, 1, 0)
        glRotatef(-y, math.cos(math.radians(x)), 0, math.sin(math.radians(x)))
        x,y,z = self.position
        glTranslatef(-x, -y, -z)
        
        #glRotatef(self.spherical[1], 1, 0, 0)
        #glRotatef(-self.spherical[0], 0, 1, 0)

    def on_draw(self):
        """ Called by pyglet to draw the canvas.

        """
        self.clear()
        self.set_3d()
        glColor3d(1, 1, 1)
        self.rootSystem.batch.draw()
        #self.draw_focused_block()
        self.set_2d()
        self.draw_labels()

    def draw_labels(self):
        """ Draw the label in the top left of the screen.

        """
        #x, y, z = self.position
        #self.label.text = '%02d (%.2f, %.2f, %.2f) %d / %d' % (pyglet.clock.get_fps(), x, y, z, len(self.rootSystem._shown), len(self.rootSystem.world))
        #self.label.draw()

        #self.rLabel.text = "%.2f, %.2f" % (self.rotation[0], self.rotation[1])
        #self.rLabel.draw()

        self.positionLabel.text = "(%d,%d,%d,%d%s,%d%s)" % (self.position[0], self.position[1], self.position[2], self.rotation[0], DEGREES, self.rotation[1], DEGREES)
        self.positionLabel.draw()

        self.actionLabel.draw()
        self.controlsLabel.draw()

        self.energyLabel.text = "Energy remaining: %d" % (ENERGY)
        self.energyLabel.draw()

def setup_fog():
    """ Configure the OpenGL fog properties.

    """
    # Enable fog. Fog "blends a fog color with each rasterized pixel fragment's
    # post-texturing color."
    glEnable(GL_FOG)
    # Set the fog color.
    #glFogfv(GL_FOG_COLOR, (GLfloat * 4)(0.5, 0.69, 1.0, 1))
    glFogfv(GL_FOG_COLOR, (GLfloat * 4)(0, 0, 0, 1))
    # Say we have no preference between rendering speed and quality.
    glHint(GL_FOG_HINT, GL_DONT_CARE)
    # Specify the equation used to compute the blending factor.
    glFogi(GL_FOG_MODE, GL_LINEAR)
    # How close and far away fog starts and ends. The closer the start and end,
    # the denser the fog in the fog range.
    glFogf(GL_FOG_START, 20.0)
    glFogf(GL_FOG_END, 60.0)


def setup():
    """ Basic OpenGL configuration.

    """
    # Set the color of "clear", i.e. the sky, in rgba.
    #glClearColor(0.5, 0.69, 1.0, 1)
    glClearColor(0.5, 0.5, 0.5, 1)
    # Enable culling (not rendering) of back-facing facets -- facets that aren't
    # visible to you.
    glEnable(GL_CULL_FACE)
    # Set the texture minification/magnification function to GL_NEAREST (nearest
    # in Manhattan distance) to the specified texture coordinates. GL_NEAREST
    # "is generally faster than GL_LINEAR, but it can produce textured images
    # with sharper edges because the transition between texture elements is not
    # as smooth."
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    setup_fog()


def main():
    window = Window(width=800, height=600, caption='PlantCraft', resizable=True)
    # Hide the mouse cursor and prevent the mouse from leaving the window.
    window.set_exclusive_mouse(True)
    setup()
    pyglet.app.run()


if __name__ == '__main__':
    main()
