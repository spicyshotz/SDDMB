# SteamDepotDownloaderModBuddy

Yet another DepotDownloader wrapper, but a little nicer.

This program was made to streamline finding manifest files, downloading the game and removing its Steam dependency, AIO.

You can use it for both downloading and playing games and also downloading workshop files by pasting their links in the search bar.

To use the program you need the following:
* Hubcap's Manifests API
* A Steam account (one you don't mind getting nuked for doing this)

Additionally, The program depends on the following projects:

* DepotDownloaderMod (SteamAutoCracks/DepotDownloaderMod)
* Steamless (atom0s/Steamless)
* uc-online2 (UnionCrax-Team/uc-online2)

> [!NOTE]  
> While I can speak for myself and state that my program's build is clean, I cannot attest to the other projects. If you are unsure, read their code and build them yourself if possible. You can, of course, build my program too using build-exe.py, or run the Python files directly without building at all.

You may use install.bat to download the projects mentioned above into the right directories if you wish, or you can do so yourself by downloading their releases / building them yourself.

* DepotDownloaderMod must be in a folder called DDM that sits beside the EXE
* Steamless must be in a folder called Steamless that sits beside the EXE
* uc-online2 must be in a folder called UC2 that sits beside the EXE

On the first run DepotDownloaderMod will ask for your Steam creds and 2FA, on later runs this will be remembered.

Downloaded manifest and depot keys files are saved to Documents\GameManifests\ for future reuse.
