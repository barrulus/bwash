{
  description = "Screenshot annotator and lightweight image editor";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        packages.default = pkgs.callPackage ./nix/package.nix { };

        apps.default = flake-utils.lib.mkApp {
          drv = self.packages.${system}.default;
        };

        devShells.default = pkgs.mkShell {
          inputsFrom = [ self.packages.${system}.default ];

          # The unwrapped development executable needs GTK's dialog schemas.
          GSETTINGS_SCHEMA_DIR = pkgs.glib.getSchemaPath pkgs.gtk4;

          packages = with pkgs; [
            tesseract
            wl-clipboard
            # Isolated GUI regression tests; not included in the application.
            dbus
            xvfb-run
            xdotool
            (python3.withPackages (ps: [ ps.pillow ]))
          ];
        };

        formatter = pkgs.nixfmt;
      }
    );
}
