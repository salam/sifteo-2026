using System.Collections;
using System.Collections.Generic;

namespace Sifteo;

public class SoundSet : IEnumerable
{
	private List<string> mSounds = new List<string>();

	internal IMsgService msgService;

	private Dictionary<int, Sound> activeSounds = new Dictionary<int, Sound>();

	internal SoundSet()
	{
		msgService = JsonRpcService.Instance;
	}

	internal void Add(string sound)
	{
		if (!mSounds.Contains(sound))
		{
			mSounds.Add(sound);
		}
	}

	IEnumerator IEnumerable.GetEnumerator()
	{
		return mSounds.GetEnumerator();
	}

	public Sound CreateSound(string name)
	{
		if (!mSounds.Contains(name))
		{
			throw new KeyNotFoundException($"sound {name} does not exist");
		}
		return new Sound(name, this);
	}

	internal void RegisterSoundHandle(Sound s, int handle)
	{
		activeSounds.Add(handle, s);
	}

	internal void HandleSoundStarted(int handle)
	{
		if (activeSounds.TryGetValue(handle, out var value))
		{
			value.HandleStarted();
		}
	}

	internal void HandleSoundStopped(int handle)
	{
		if (activeSounds.TryGetValue(handle, out var value))
		{
			value.HandleStopped();
			activeSounds.Remove(handle);
		}
	}
}
