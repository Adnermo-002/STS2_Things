using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Multiplayer.Serialization;
using MegaCrit.Sts2.Core.Multiplayer.Transport;

namespace STS2_Things.Config;

/// <summary>A bounded, host-only snapshot on the same reliable channel as run start.</summary>
public struct ThingsConfigSnapshotMessage : INetMessage
{
    public const int Protocol = 1;
    public static readonly uint Schema = BinaryPrimitives.ReadUInt32LittleEndian(SHA256.HashData(
        Encoding.UTF8.GetBytes(string.Join("|", ThingsModConfig.Entries.Select(entry => $"{entry.Key}:{entry.Default.GetType().Name}")))));

    public int Version;
    public uint SchemaHash;
    public uint Revision;
    public bool Locked;
    public int[] Values;

    public bool ShouldBroadcast => false;
    public NetTransferMode Mode => NetTransferMode.Reliable;
    public LogLevel LogLevel => LogLevel.Debug;
    public bool ShouldBuffer => false;

    public void Serialize(PacketWriter writer)
    {
        writer.WriteInt(Version);
        writer.WriteUInt(SchemaHash);
        writer.WriteUInt(Revision);
        writer.WriteBool(Locked);
        writer.WriteByte((byte)Values.Length);
        foreach (int value in Values) writer.WriteInt(value);
    }

    public void Deserialize(PacketReader reader)
    {
        Values = [];
        if (reader.Buffer.Length * 8 - reader.BitPosition < 105) return;
        Version = reader.ReadInt();
        SchemaHash = reader.ReadUInt();
        Revision = reader.ReadUInt();
        Locked = reader.ReadBool();
        int count = reader.ReadByte();
        if (count != ThingsModConfig.Entries.Count || reader.Buffer.Length * 8 - reader.BitPosition < count * 32) return;
        Values = new int[count];
        for (int i = 0; i < count; i++) Values[i] = reader.ReadInt();
    }

    public bool IsValid()
    {
        if (Version != Protocol || SchemaHash != Schema || Revision == 0 || Values?.Length != ThingsModConfig.Entries.Count)
            return false;
        var forcedSlots = new HashSet<string>();
        for (int i = 0; i < Values.Length; i++)
        {
            ThingsModConfig.Entry entry = ThingsModConfig.Entries[i];
            if (entry.Default is bool ? Values[i] is not (0 or 1) : Values[i] < entry.Min || Values[i] > entry.Max)
                return false;
            if (Values[i] == 1 && entry.Slot is { } slot && entry.Key.EndsWith("Forced", StringComparison.Ordinal))
            {
                string enabled = entry.Key[..^"Forced".Length] + "Enabled";
                int index = ThingsModConfig.Entries.ToList().FindIndex(candidate => candidate.Key == enabled);
                if (!forcedSlots.Add(slot) || index < 0 || Values[index] != 1) return false;
            }
        }
        return true;
    }
}
