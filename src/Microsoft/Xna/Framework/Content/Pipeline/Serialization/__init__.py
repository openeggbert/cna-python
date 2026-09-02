"""Microsoft.Xna.Framework.Content.Pipeline.Serialization.

A namespace with no types of its own: XNA declares only its two children,
``Compiler`` -- which writes ``.xnb`` -- and ``Intermediate`` -- which writes the
XML a build keeps between runs. They are separate imports so that a build tool
that only compiles never loads the XML machinery, and the other way round.
"""
