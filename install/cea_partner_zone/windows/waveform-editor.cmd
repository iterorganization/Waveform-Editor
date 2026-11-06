@echo off
rem Double-click this file to start the Waveform-Editor GUI from altair in your browser.
rem It runs waveform-editor.ps1, which must be in the same folder.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0waveform-editor.ps1" %*
