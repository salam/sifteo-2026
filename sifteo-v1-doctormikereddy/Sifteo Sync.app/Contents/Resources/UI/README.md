This directory contains the UI of Sifteo Sync, implemented in HTML, CSS,
JavaScript and other web technologies.

### JavaScript

#### Package Management

Sifteo Sync uses [volo](http://volojs.org/) for package management.

To install a new dependency, execute `volo add`:

    $ volo add anchorjs/ajax
    
This above command will fetch the module, as well as any dependencies, from
GitHub and install them into `js/lib`.

To update an existing dependency, execute `volo add -f`:

    $ volo add -f anchorjs/ajax

#### Package Management using Git Subtree

Unfortunately, `volo` is currently unable to add modules from Bitbucket.  For
modules that are hosted on Bitbucket, `git subtree` is used pull code into the
`js/lib` directory.

Note that `git subtree` must be run from the top level of the working tree.

##### siftsystem

siftsystem was added as a dependency using the following command:

    $ git subtree add -P html/js/lib/siftsystem --squash git@bitbucket.org:sifteo/js-siftsystem.git master

To update to a more recent version:

    $ git subtree pull -P html/js/lib/siftsystem --squash git@bitbucket.org:sifteo/js-siftsystem.git master

When modifications are made to the module within the Sifteo Sync repository,
a patch can be submitted to an upstream branch named "patch-1" using the
following command:
    
    $ git subtree push -P html/js/lib/siftsystem --annotate="[Sifteo Sync]" git@bitbucket.org:sifteo/js-siftsystem.git patch-1
