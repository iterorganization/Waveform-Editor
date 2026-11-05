Waveform-Editor from your Windows laptop
========================================

The GUI runs on altair, and the browser of your laptop shows it, which is much faster
than a browser inside x2go.

Once: copy the two files waveform-editor.cmd and waveform-editor.ps1 to a folder on
your laptop, for example with this command in PowerShell (replace MS013565 with
your own login):

    scp MS013565@altair.partenaires.cea.fr:/home/MS013565/public/waveform-editor-nice/windows/waveform-editor.* $HOME\Desktop\

Each time: double-click waveform-editor.cmd.
  - The first time it asks for your login on altair, and remembers it.
  - Log in as for x2go (password or key).
  - The browser opens by itself after about 10 to 20 seconds.
  - To stop: close the window (or press Ctrl+C in it).

If your login was mistyped, delete the file .waveform-editor-login in your home
folder (C:\Users\<you>) and start again.
