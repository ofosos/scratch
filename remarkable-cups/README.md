# What is it?

This is a custom backend that uses
[rmapi](https://github.com/juruen/rmapi) to print files from your
local Linux desktop directly to the remarkable cloud.

# Usage

This contains a `.drv` file that is compiled to result in the `.ppd`
file. This driver/filter presents the remarkable as a PDF device and
sets the page size. C.f. [Ghostscript
docs](https://ghostscript.com/doc/cups/libs/filter/postscript-driver.shtml)
and
[ppdc](https://ghostscript.com/doc/cups/libs/filter/ppd-compiler.shtml),
a tool that Ghostscript ships. To compile the driver:

```
ppdc remarkable.drv
```

Place the resulting `.ppd` somewhere where cups can find it.

Adapt the path to `rmapi` in `remarkable.sh` to your needs and make
sure the user cups executes this script with has the corresponding
`.rmapi` credentials in their `$HOME/`.

Now copy `remarkable.sh` into `/usr/lib/cups/backend` and rename it to
just `remarkable`.

Create your printer and you should be good. The backend takes a URL
like `remarkable:/Print` as a parameter. It will push all your
files into the folder secified in that URL.

Note: The folder (E.g. "/Print") must exist on your reMarkable already.

```
# Compile ppd driver & copy to somewhere where CUPS can find it.
ppdc remarkable.drv; sudo cp ppd/remarkable.ppd /usr/share/cups/model/

# Copy & rename CUPS backend script
sudo cp remarkable.sh /usr/lib/cups/backend/remarkable

# Secure permissions
sudo chown root:root /usr/lib/cups/backend/remarkable
sudo chmod 700 /usr/lib/cups/backend/remarkable

# Add/Update "Remarkable" cups printer
lpadmin -L 'Cloud Printer' -D 'my remarkable' -p "reMarkable" -E -v 'remarkable:/Print'
```

# Notes

The cups user needs permissions to connect to the internet. This might
need adjustments to the Cups config, or you might need to run the
script with a custom user. If you run as a custom user, you might need
to adapt the path to rmapi.
