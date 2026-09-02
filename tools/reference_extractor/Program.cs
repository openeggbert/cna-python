// Reference-profile metadata extractor.
//
// Reads Microsoft XNA reference assemblies with System.Reflection.Metadata
// through a MetadataLoadContext and emits the strict-profile contract JSON the
// verifier consumes.  The tool is a generator, not a gate: its output is
// checked in and every profile pins the sha256 of the assemblies it was read
// from.  Nothing here is redistributed -- only measured.
//
// The tool proves itself by re-deriving the already-accepted
// xna40-windows-runtime contract: see tools/api_compat/compare_contracts.py.

using System.Collections.Immutable;
using System.Globalization;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;

const int SchemaVersion = 2;

var options = ArgumentParser.Parse(args);
if (options is null)
{
    Console.Error.WriteLine(
        "Usage: ReferenceExtractor --profile <profile.json> --output <contract.json> [--pin-hashes]");
    return 2;
}

JsonNode profile = JsonNode.Parse(File.ReadAllText(options.ProfilePath))
    ?? throw new InvalidOperationException($"empty profile: {options.ProfilePath}");

string profileName = (string)profile["name"]!;
string profileDirectory = Path.GetDirectoryName(Path.GetFullPath(options.ProfilePath))!;
string assemblyRoot = Expand((string?)profile["assemblyRoot"] ?? ".", profileDirectory);

var assemblyNames = profile["referenceAssemblies"]!.AsArray()
    .Select(node => (string)node!).ToImmutableArray();

var resolveDirectories = new List<string> { assemblyRoot };
if (profile["resolveDirectories"] is JsonArray extra)
{
    foreach (JsonNode? node in extra)
    {
        resolveDirectories.Add(Expand((string)node!, profileDirectory));
    }
}

string? coreAssemblyName = (string?)profile["coreAssemblyName"];

var selectedPaths = assemblyNames
    .Select(name => Path.Combine(assemblyRoot, name))
    .ToImmutableArray();

foreach (string path in selectedPaths)
{
    if (!File.Exists(path))
    {
        Console.Error.WriteLine($"MISSING_REFERENCE_ASSEMBLY {path}");
        return 3;
    }
}

var searchPaths = new List<string>();
foreach (string directory in resolveDirectories)
{
    if (!Directory.Exists(directory))
    {
        continue;
    }
    foreach (string candidate in Directory.EnumerateFiles(directory, "*.dll"))
    {
        if (HasManagedMetadata(candidate))
        {
            searchPaths.Add(candidate);
        }
    }
}

var resolver = new PathAssemblyResolver(searchPaths.Distinct(StringComparer.Ordinal));
using var context = coreAssemblyName is null
    ? new MetadataLoadContext(resolver)
    : new MetadataLoadContext(resolver, coreAssemblyName);

var assemblies = selectedPaths.Select(context.LoadFromAssemblyPath).ToImmutableArray();

var types = new List<JsonObject>();
foreach (Assembly assembly in assemblies)
{
    foreach (Type type in assembly.GetTypes())
    {
        if (!TypeModel.IsVisibleOutsideAssembly(type))
        {
            continue;
        }
        types.Add(TypeModel.Describe(type));
    }
}

types.Sort((left, right) => string.CompareOrdinal((string)left["name"]!, (string)right["name"]!));

var referenceSha256 = new JsonObject();
foreach (string path in selectedPaths)
{
    referenceSha256[Path.GetFileName(path)] =
        Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();
}

int memberCount = types.Sum(type => type["members"]!.AsArray().Count);

var contract = new JsonObject
{
    ["schemaVersion"] = SchemaVersion,
    ["profile"] = profileName,
    ["types"] = new JsonArray(types.Select(type => (JsonNode)type).ToArray()),
};

var serializer = new JsonSerializerOptions { WriteIndented = true };
Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(options.OutputPath))!);
File.WriteAllText(options.OutputPath, contract.ToJsonString(serializer) + "\n");

Console.WriteLine($"PROFILE={profileName}");
Console.WriteLine($"REFERENCE_ASSEMBLIES={assemblyNames.Length}");
Console.WriteLine($"REFERENCE_TYPES={types.Count}");
Console.WriteLine($"REFERENCE_MEMBERS={memberCount}");
foreach (KeyValuePair<string, JsonNode?> entry in referenceSha256)
{
    Console.WriteLine($"SHA256 {entry.Key} {(string)entry.Value!}");
}
return 0;

static bool HasManagedMetadata(string path)
{
    try
    {
        using FileStream stream = File.OpenRead(path);
        using var reader = new System.Reflection.PortableExecutable.PEReader(stream);
        return reader.HasMetadata;
    }
    catch (Exception)
    {
        return false;
    }
}

static string Expand(string path, string relativeTo)
{
    if (path.StartsWith("~/", StringComparison.Ordinal))
    {
        string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        return Path.GetFullPath(Path.Combine(home, path[2..]));
    }
    return Path.IsPathRooted(path)
        ? Path.GetFullPath(path)
        : Path.GetFullPath(Path.Combine(relativeTo, path));
}

internal sealed record ExtractorOptions(string ProfilePath, string OutputPath);

internal static class ArgumentParser
{
    public static ExtractorOptions? Parse(string[] args)
    {
        string? profile = null;
        string? output = null;
        for (int index = 0; index < args.Length; index++)
        {
            switch (args[index])
            {
                case "--profile" when index + 1 < args.Length:
                    profile = args[++index];
                    break;
                case "--output" when index + 1 < args.Length:
                    output = args[++index];
                    break;
                default:
                    return null;
            }
        }
        return profile is null || output is null ? null : new ExtractorOptions(profile, output);
    }
}

internal static class TypeModel
{
    private const BindingFlags Declared =
        BindingFlags.Public | BindingFlags.NonPublic |
        BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly;

    public static bool IsVisibleOutsideAssembly(Type type)
    {
        if (type.Name == "<Module>")
        {
            return false;
        }
        while (type.IsNested)
        {
            if (!type.IsNestedPublic && !type.IsNestedFamily && !type.IsNestedFamORAssem)
            {
                return false;
            }
            type = type.DeclaringType!;
        }
        return type.IsPublic;
    }

    public static JsonObject Describe(Type type)
    {
        string kind = type.IsEnum ? "enum"
            : type.IsInterface ? "interface"
            : type.IsValueType ? "struct"
            : "class";

        Type[] direct = DirectInterfaces(type);
        var all = new SortedSet<string>(StringComparer.Ordinal);
        foreach (Type candidate in InterfaceClosure(type))
        {
            all.Add(Format(candidate));
        }

        var members = new JsonArray();
        foreach (JsonObject member in Constructors(type)) members.Add((JsonNode)member);
        foreach (JsonObject member in Methods(type)) members.Add((JsonNode)member);
        foreach (JsonObject member in Properties(type)) members.Add((JsonNode)member);
        foreach (JsonObject member in Events(type)) members.Add((JsonNode)member);
        foreach (JsonObject member in Fields(type)) members.Add((JsonNode)member);

        return new JsonObject
        {
            ["name"] = FormatDefinitionName(type),
            ["kind"] = kind,
            ["flags"] = HasFlagsAttribute(type),
            ["sealed"] = type.IsSealed,
            ["underlyingType"] = type.IsEnum ? Format(Enum.GetUnderlyingType(type)) : null,
            ["baseType"] = type.BaseType is null ? null : Format(type.BaseType),
            ["interfaces"] = new JsonArray(all.Select(name => (JsonNode)name!).ToArray()),
            ["directInterfaces"] = new JsonArray(
                direct.Select(Format).OrderBy(name => name, StringComparer.Ordinal)
                      .Select(name => (JsonNode)name!).ToArray()),
            ["genericParameters"] = GenericParameters(
                type.IsGenericTypeDefinition ? type.GetGenericArguments() : Type.EmptyTypes),
            ["members"] = members,
        };
    }

    private static bool HasFlagsAttribute(Type type)
    {
        foreach (CustomAttributeData attribute in type.GetCustomAttributesData())
        {
            if (attribute.AttributeType.FullName == "System.FlagsAttribute")
            {
                return true;
            }
        }
        return false;
    }

    /// A metadata reader reports the interfaces a type declares plus the ones its
    /// base type reports, but does not always re-expand an interface's own bases
    /// when that interface comes from another assembly.  IEnumerable`1 is the
    /// case that matters here: a type declaring it also implements IEnumerable.
    /// The closure is therefore computed rather than trusted.
    public static IReadOnlyCollection<Type> InterfaceClosure(Type type)
    {
        var seen = new HashSet<Type>();
        var pending = new Stack<Type>();
        foreach (Type candidate in type.GetInterfaces())
        {
            pending.Push(candidate);
        }
        for (Type? current = type.BaseType; current is not null; current = current.BaseType)
        {
            foreach (Type candidate in current.GetInterfaces())
            {
                pending.Push(candidate);
            }
        }
        while (pending.Count > 0)
        {
            Type candidate = pending.Pop();
            if (!seen.Add(candidate))
            {
                continue;
            }
            foreach (Type nested in candidate.GetInterfaces())
            {
                pending.Push(nested);
            }
        }
        return seen;
    }

    private static Type[] DirectInterfaces(Type type)
    {
        var inherited = new HashSet<Type>();
        if (type.BaseType is not null)
        {
            foreach (Type candidate in InterfaceClosure(type.BaseType))
            {
                inherited.Add(candidate);
            }
        }
        var declared = new List<Type>();
        foreach (Type candidate in type.GetInterfaces())
        {
            if (inherited.Contains(candidate))
            {
                continue;
            }
            declared.Add(candidate);
        }
        // An interface reachable only through another declared interface is not direct.
        var throughOthers = new HashSet<Type>();
        foreach (Type candidate in declared)
        {
            foreach (Type nested in InterfaceClosure(candidate))
            {
                throughOthers.Add(nested);
            }
        }
        return declared.Where(candidate => !throughOthers.Contains(candidate)).ToArray();
    }

    private static bool Visible(MethodBase method) =>
        method.IsPublic || method.IsFamily || method.IsFamilyOrAssembly;

    private static bool Visible(FieldInfo field) =>
        field.IsPublic || field.IsFamily || field.IsFamilyOrAssembly;

    private static string Access(MethodBase method) =>
        method.IsPublic ? "public" : method.IsFamily ? "protected" : "protected-internal";

    private static IEnumerable<JsonObject> Constructors(Type type)
    {
        foreach (ConstructorInfo constructor in type.GetConstructors(Declared))
        {
            if (!Visible(constructor))
            {
                continue;
            }
            yield return new JsonObject
            {
                ["kind"] = "constructor",
                ["name"] = constructor.Name,
                ["static"] = constructor.IsStatic,
                ["access"] = Access(constructor),
                ["returnType"] = null,
                ["genericParameters"] = new JsonArray(),
                ["parameters"] = Parameters(constructor.GetParameters()),
            };
        }
    }

    private static IEnumerable<JsonObject> Methods(Type type)
    {
        var accessors = new HashSet<string>(StringComparer.Ordinal);
        foreach (PropertyInfo property in type.GetProperties(Declared))
        {
            foreach (MethodInfo accessor in property.GetAccessors(nonPublic: true))
            {
                accessors.Add(accessor.Name);
            }
        }
        foreach (EventInfo declared in type.GetEvents(Declared))
        {
            foreach (MethodInfo? accessor in new[]
                     { declared.GetAddMethod(true), declared.GetRemoveMethod(true), declared.GetRaiseMethod(true) })
            {
                if (accessor is not null)
                {
                    accessors.Add(accessor.Name);
                }
            }
        }

        foreach (MethodInfo method in type.GetMethods(Declared))
        {
            if (!Visible(method) || accessors.Contains(method.Name))
            {
                continue;
            }
            yield return new JsonObject
            {
                ["kind"] = "method",
                ["name"] = method.Name,
                ["static"] = method.IsStatic,
                ["access"] = Access(method),
                ["returnType"] = Format(method.ReturnType),
                ["genericParameters"] = GenericParameters(
                    method.IsGenericMethodDefinition ? method.GetGenericArguments() : Type.EmptyTypes),
                ["parameters"] = Parameters(method.GetParameters()),
            };
        }
    }

    private static IEnumerable<JsonObject> Properties(Type type)
    {
        foreach (PropertyInfo property in type.GetProperties(Declared))
        {
            MethodInfo? getter = property.GetGetMethod(nonPublic: true);
            MethodInfo? setter = property.GetSetMethod(nonPublic: true);
            bool getVisible = getter is not null && Visible(getter);
            bool setVisible = setter is not null && Visible(setter);
            if (!getVisible && !setVisible)
            {
                continue;
            }
            MethodInfo shape = (getVisible ? getter : setter)!;
            yield return new JsonObject
            {
                ["kind"] = "property",
                ["name"] = property.Name,
                ["type"] = Format(property.PropertyType),
                ["static"] = shape.IsStatic,
                ["get"] = getVisible,
                ["set"] = setVisible,
                ["getAccess"] = getVisible ? Access(getter!) : null,
                ["setAccess"] = setVisible ? Access(setter!) : null,
                ["parameters"] = Parameters(property.GetIndexParameters()),
            };
        }
    }

    private static IEnumerable<JsonObject> Events(Type type)
    {
        foreach (EventInfo declared in type.GetEvents(Declared))
        {
            MethodInfo? add = declared.GetAddMethod(nonPublic: true);
            MethodInfo? remove = declared.GetRemoveMethod(nonPublic: true);
            bool addVisible = add is not null && Visible(add);
            bool removeVisible = remove is not null && Visible(remove);
            if (!addVisible && !removeVisible)
            {
                continue;
            }
            yield return new JsonObject
            {
                ["kind"] = "event",
                ["name"] = declared.Name,
                ["type"] = declared.EventHandlerType is null ? null : Format(declared.EventHandlerType),
                ["static"] = (addVisible ? add! : remove!).IsStatic,
                ["add"] = addVisible,
                ["remove"] = removeVisible,
            };
        }
    }

    private static IEnumerable<JsonObject> Fields(Type type)
    {
        foreach (FieldInfo field in type.GetFields(Declared))
        {
            if (!Visible(field))
            {
                continue;
            }
            bool constant = field.IsLiteral;
            yield return new JsonObject
            {
                ["kind"] = "field",
                ["name"] = field.Name,
                ["type"] = Format(field.FieldType),
                ["static"] = field.IsStatic,
                ["constant"] = constant,
                ["value"] = constant ? FormatConstant(field.GetRawConstantValue()) : null,
            };
        }
    }

    private static string? FormatConstant(object? value) => value switch
    {
        null => null,
        float single => single.ToString("G7", CultureInfo.InvariantCulture),
        double dbl => dbl.ToString("G15", CultureInfo.InvariantCulture),
        bool flag => flag ? "True" : "False",
        string text => text,
        IFormattable formattable => formattable.ToString(null, CultureInfo.InvariantCulture),
        _ => value.ToString(),
    };

    private static JsonArray GenericParameters(Type[] parameters)
    {
        var array = new JsonArray();
        foreach (Type parameter in parameters)
        {
            var special = new JsonArray();
            GenericParameterAttributes attributes =
                parameter.GenericParameterAttributes & GenericParameterAttributes.SpecialConstraintMask;
            if (attributes.HasFlag(GenericParameterAttributes.ReferenceTypeConstraint)) special.Add((JsonNode)"class");
            if (attributes.HasFlag(GenericParameterAttributes.NotNullableValueTypeConstraint)) special.Add((JsonNode)"struct");
            if (attributes.HasFlag(GenericParameterAttributes.DefaultConstructorConstraint)) special.Add((JsonNode)"new");

            var constraints = new JsonArray();
            foreach (string constraint in parameter.GetGenericParameterConstraints()
                         .Select(Format).OrderBy(name => name, StringComparer.Ordinal))
            {
                constraints.Add((JsonNode)constraint);
            }

            array.Add((JsonNode)new JsonObject
            {
                ["name"] = parameter.Name,
                ["position"] = parameter.GenericParameterPosition,
                ["specialConstraints"] = special,
                ["typeConstraints"] = constraints,
            });
        }
        return array;
    }

    private static JsonArray Parameters(ParameterInfo[] parameters)
    {
        var array = new JsonArray();
        foreach (ParameterInfo parameter in parameters)
        {
            array.Add((JsonNode)new JsonObject
            {
                ["name"] = parameter.Name ?? "",
                ["type"] = Format(parameter.ParameterType),
                ["ref"] = parameter.ParameterType.IsByRef,
                ["out"] = parameter.IsOut,
                ["in"] = parameter.IsIn,
                ["optional"] = parameter.IsOptional,
            });
        }
        return array;
    }

    public static string FormatDefinitionName(Type type)
    {
        string name = type.Name;
        if (type.IsNested)
        {
            return FormatDefinitionName(type.DeclaringType!) + "+" + name;
        }
        return string.IsNullOrEmpty(type.Namespace) ? name : type.Namespace + "." + name;
    }

    public static string Format(Type type)
    {
        if (type.IsGenericParameter)
        {
            return (type.DeclaringMethod is not null ? "!!" : "!") + type.GenericParameterPosition;
        }
        if (type.IsByRef)
        {
            return Format(type.GetElementType()!) + "&";
        }
        if (type.IsPointer)
        {
            return Format(type.GetElementType()!) + "*";
        }
        if (type.IsArray)
        {
            int rank = type.GetArrayRank();
            return Format(type.GetElementType()!) + "[" + new string(',', rank - 1) + "]";
        }
        if (type.IsConstructedGenericType)
        {
            string definition = FormatDefinitionName(type.GetGenericTypeDefinition());
            IEnumerable<string> arguments = type.GetGenericArguments().Select(Format);
            return definition + "[" + string.Join(",", arguments) + "]";
        }
        return FormatDefinitionName(type);
    }
}
