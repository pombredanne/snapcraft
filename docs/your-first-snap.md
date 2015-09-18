# Snapcraft Tutorial

Let's make a snap from scratch using Snapcraft! We'll pick something a little
interesting: a webcam server.

## Preparation

You'll want a webcam and a Snappy device. We'll assume you have those,
but if you need help setting up a Snappy install, there is help
[online](https://developer.ubuntu.com/en/snappy/start/).

(Even if you don't have either of those, you can still follow along. You just
won't be able to use the final snap package you create. But you'll get to see
how Snapcraft works, which is still super rewarding.)

You should also install Snapcraft:

    $ sudo add-apt-repository ppa:snappy-dev/tools
    $ sudo apt-get update
    $ sudo apt-get install snapcraft

## Approach

This example is easy because we won't be doing much of the heavy lifting
ourselves. We're going to integrate a couple pieces of code together to make
an interesting app.

Namely, we'll combine a web server with a webcam program and combine
them to serve a new frame every ten seconds.

> The resulting package is also part of the examples directory in the
> [snapcraft sources](http://bazaar.launchpad.net/~snappy-dev/snapcraft/core/files/head:/examples/webcam-webui/)

### The Web Server

Go has a simple web server in its standard libraries. So let's just use that.

It's trivial to write a complete (but basic) web server in a few lines:

    package main
    import "net/http"
    func main() {
        panic(http.ListenAndServe(":8080", http.FileServer(http.Dir("."))))
    }

This will serve the current directory on port `:8080`. If there is an
`index.html` in the current directory, it will be served. Otherwise a
directory listing will be shown.

This code is hosted on a simple GitHub
[repository](https://github.com/mikix/golang-static-http).

### The Webcam Program

There is a webcam program provided in the Ubuntu archives called `fswebcam`.
It has a lot of neat features. But all we'll be needing for now is its ability
to take a webcam freeze frame and drop it to a file by calling it like so:

    $ fswebcam output.jpg

## Snapcraft Recipe

OK, let's create a Snapcraft recipe that combines the above programs into a
useful snap.

Snapcraft reads a single file, `snapcraft.yaml`, which tells it how to combine
code. It contains a list of `parts`, or pieces of code, and some metadata for
the final snap it will create. But let's not worry about the metadata yet.

### Initializing a project

To get started with a base template create a folder that will hold your
project, and initialize it:

    $ mkdir webcam-webui
    $ cd webcam-webui
    $ snapcraft init

then open the created snapcraft.yaml and edit the templated values for `name`,
`version`, `vendor`, `summary` and `description`. You can make it look like
this:

    name: webcam-webui
    version: 1
    vendor: You <you@example.com>
    summary: Webcam web UI
    description: Exposes your webcam over a web UI
    icon: icon.png

and copy over an icon to `icon.png` or change the path accordingly (if you
change the path just make sure it is part of your project directory and that
the path is relative to be able to share your snapcrafting):

    $ cp /usr/share/icons/hicolor/64/mimetypes/text-x-apport.png ./icon.png

If you run `snapcraft` now, it will complain about not having any `parts`.

We will look more into this metadata in a bit, but first let's look at adding
some `parts`.

### Web Server Part

Let's start with the web server.

    parts:
      cam:
        type: go-project
        source: git://github.com/mikix/golang-static-http

You've just defined a `part` inside `parts` named `cam`, but you
could call it anything. That part has a two options: A `type` option that
tells Snapcraft how to interpret the part (in this case, it's a Go project),
and a `source` option telling Snapcraft where to download the code.

Go ahead and append the above contents to your recently created
`snapcraft.yaml`.

Now we can build and "stage" this recipe. Staging just means putting the output
of the parts in a common folder that has the same layout as the snap we'll
eventually create. It lets you look at how the snap is constructed and make
sure everything is in place.

    $ snapcraft stage

You'll see a bunch of output, including Snapcraft downloading the Go compiler
if not already installed on your host build environment.
It will use this to compile the code found on GitHub. Eventually when it is
done, you'll be able to inspect the `./stage` folder and see the web server
executable sitting in `./stage/bin`:

    $ ls stage/bin
    golang-static-http

### Adding an Ubuntu dependency to a part.

Now let's add the webcam program `fswebcam` to our snap. Edit `snapcraft.yaml`
to make the `cam` part look like:

    parts:
      cam:
        type: go-project
        source: git://github.com/mikix/golang-static-http
        stage-packages:
          - fswebcam

We've just added a new property to the `cam` part called `stage-packages` which
contains a yaml list with any supporting Ubuntu package we want; in this case
our list has one element with an entry for the `fswebcam` Ubuntu `deb` based
package.

Now let's stage our recipe again (and force it to go through the lifecycle).

    $ snapcraft stage --force

You'll also see Snapcraft downloading and unpacking all the Ubuntu packages
into your snap. If you look at `./stage`, you'll see a lot more files now:

    $ ls stage
    bin  etc  lib  usr  var

### A copy Part

OK, so we have the two programs in our staging area. But how do we make them
work together?

We'll write a tiny little script that runs the server and `fswebcam` together:

    #!/bin/sh
    set -e

    cd "$SNAP_APP_DATA_PATH"

    golang-static-http &

    while :; do
        fswebcam shot.jpeg
        sleep 10
    done

Save the above as `webcam-webui` and make it executable:

    $ chmod a+x webcam-webui

Alright, let's put this script in our snap too:

    parts:
      cam:
        type: go-project
        source: git://github.com/mikix/golang-static-http
        stage-packages:
          - fswebcam
      glue:
        type: copy
        files:
          webcam-webui: bin/webcam-webui

A part of type `copy` takes a list of files to just directly copy without
building or downloading anything. In this case, we just want to put our glue
script in the `bin/` directory.

If we run Snapcraft again, we won't be surprised:

    $ snapcraft stage

We should now see both the web server and our script in stage/bin (the webcam
program is in stage/usr/bin since it came from Ubuntu):

    $ ls stage/bin
    golang-static-http  webcam-webui

### Filesets

Some files in `./stage` could be needed for building dependent parts during the
staging phase and some of these would be useful for the resulting snap. In
this case we don't need some of these for either staging or the resulting snap,
so let's add some filesets for the snap.

Edit `snapcraft.yaml` once more to make the `cam` part in `parts` to look like:

    parts:
      cam:
        type: go-project
        source: git://github.com/mikix/golang-static-http
        stage-packages:
          - fswebcam
        filesets:
          fswebcam:
            - usr/bin/fswebcam
            - lib
            - usr/lib
          go-server:
            - bin/golang-*
        snap:
          - $fswebcam
          - $go-server
      glue:
        type: copy
        files:
          webcam-webui: bin/webcam-webui

What we did was add two `filesets`, one named `fswebcam` and another one named
`go-server` and then added a `snap` entry referencing these two filesets with
`$`. All these filesets are inclusion based filesets, you can use `*` to glob
many files and directories (if `*` is the first character, it needs to be
quoted e.g.; `'*'`). An exclusion can be added by prefixing the file
with a `-`. Additionally, you don't need to define a fileset, you can explicitly
mention the file, directory or match under `snap` or `stage`.

### Extending the Metadata

The defined values in `snapcraft.yaml` are used to build the corresponding
`meta` directory that holds all the package information.

You can read all about the resulting [format of this metadata](https://developer.ubuntu.com/en/snappy/guides/packaging-format-apps/),
but we'll assume here that you're already familiar.

The templated values when `snapcraft init` was run did not hold any `parts`
which we've filled along the way. It also did not define any `services` or
`binaries` which we will be adding now

Edit `snapcraft.yaml` once more and add the `services` and `binaries` entry,
your resulting `snapcraft.yaml` should look very similar to:

    name: webcam-webui
    version: 1
    vendor: You <you@example.com>
    summary: Webcam web UI
    description: Exposes your webcam over a web UI
    icon: icon.png
    services:
    - name: webcam-webui
      start: bin/webcam-webui

    parts:
      golang-static-http:
        plugin: go-project
        source: git://github.com/mikix/golang-static-http
      fswebcam:
        plugin: ubuntu
      glue:
        plugin: copy
        files:
          webcam-webui: bin/webcam-webui

and tell Snapcraft to actually make the snap package:

    $ snapcraft

You should now have a `webcam-webui_1_amd64.snap` file sitting in your
directory (assuming you are running on amd64). Congratulations!


## Next steps

Well done, your first snap using snapcraft is ready. If you want to check out
a few examples for reference or to get inspired, have a look at the
`examples` directory in the source directory of snapcraft:

    bzr branch lp:snapcraft
    cd snapcraft/examples

In `examples/` you can find a diverse set of examples which should help you
get started on your own projects.

If you should have any more questions, ask us on

 * `#snappy` on `irc.freenode.net` or
 * the [snappy-app-devel](https://lists.ubuntu.com/mailman/listinfo/snappy-app-devel)
   mailing list