{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };
  outputs = { self, nixpkgs, ... }: {
    packages.x86_64-linux = let
      pkgs = import nixpkgs {
        system = "x86_64-linux";
      };
    in {
      traythingy = pkgs.python3Packages.buildPythonApplication {
        pname = "traythingy";
        version = "0.0.1";
        pyproject = true;

        src = ./.;

        nativeBuildInputs = [
          pkgs.qt5.wrapQtAppsHook
          pkgs.python3Packages.setuptools
        ];
        propagatedBuildInputs = [
          pkgs.python3Packages.pyqt5
          pkgs.python3Packages.qscintilla
          pkgs.libsForQt5.qtbase
        ];

        preFixup = ''
          makeWrapperArgs+=("''${qtWrapperArgs[@]}")
        '';

      };

      default = self.packages.x86_64-linux.traythingy;
    };
  };
}
