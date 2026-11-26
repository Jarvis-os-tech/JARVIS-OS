# JARVIS KVM preview

Run `packaging/vm/launch` to reopen the existing guest after shutdown. The window auto-logs in as `jarvis`. Its local preview password is `jarvis`. Use Super+Space for applications, Super+Return for a terminal, and Super+L to lock. To shut down cleanly, run `systemctl poweroff` in the guest terminal.

The preview uses two virtual CPUs, 2 GiB of RAM, a sparse 10 GiB ext4 disk and a direct-boot Linux kernel. QEMU runs as your user with KVM, SDL and virtio-vga-gl. The launcher attaches no network adapter and shares no host directories.

## Rebuild on Arch

Build the session package with `packaging/build-jarvis-de`, then pass its absolute package filename to `packaging/vm/build`. The builder uses core, extra and Omarchy repository databases and your configured Arch mirror. It verifies the distribution archives before an isolated installer VM runs pacman. It needs QEMU, KVM access, fakeroot, mkinitcpio-busybox, cpio, gzip, e2fsprogs and the Arch packaging tools. The graphical launcher needs QEMU's SDL and virtio-vga-gl modules.

The default output is `packaging/dist/vm`. Set `JARVIS_VM_DIR` to a new directory for a separate guest and pass the same setting to the launcher. The builder refuses to overwrite an existing desktop disk. The first graphical login records the home screen and launcher under the guest user's home directory.
