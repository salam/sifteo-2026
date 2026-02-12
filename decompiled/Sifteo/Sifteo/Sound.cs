using System;
using System.Collections.Generic;
using Sifteo.MathExt;

namespace Sifteo;

public class Sound
{
	private int handle;

	private bool handleIsValid;

	private SoundSet parent;

	private IMsgService msgService;

	public string Name { get; private set; }

	public bool IsPlaying
	{
		get
		{
			if (handleIsValid)
			{
				return !IsPaused;
			}
			return false;
		}
	}

	public bool IsPaused { get; internal set; }

	public event SoundStoppedHandler StoppedEvent;

	public event SoundStartedHandler StartedEvent;

	public static void PauseAll()
	{
		JsonRpcService.Instance.Call("sound.pauseAll", null);
	}

	public static void ResumeAll()
	{
		JsonRpcService.Instance.Call("sound.resumeAll", null);
	}

	public static void StopAll()
	{
		JsonRpcService.Instance.Call("sound.stopAll", null);
	}

	internal Sound(string name, SoundSet parent)
	{
		Name = name;
		this.parent = parent;
		msgService = JsonRpcService.Instance;
	}

	public void Play(float volume, int loops = 0)
	{
		Play(volume, volume, loops);
	}

	public void Play(float volumeLeft, float volumeRight, int loops = 0)
	{
		if (IsPlaying)
		{
			Log.Warning("Sound: already playing");
			return;
		}
		msgService.Call("sound.play", PlayResponseHandler, Name, volumeLeft, volumeRight, loops);
	}

	private void PlayResponseHandler(object error, Dictionary<string, object> results)
	{
		if (error == null && results.TryGetValue("handle", out var value))
		{
			handle = (int)value;
			handleIsValid = true;
			parent.RegisterSoundHandle(this, handle);
		}
	}

	public void Stop()
	{
		if (!handleIsValid)
		{
			Log.Warning("Sound: already stopped");
			return;
		}
		IsPaused = false;
		handleIsValid = false;
		msgService.Call("sound.stop", null, handle);
	}

	public void Pause()
	{
		if (IsPaused)
		{
			Log.Warning("Sound: already paused");
			return;
		}
		if (!handleIsValid)
		{
			throw new InvalidOperationException("Sound: can't pause when stopped");
		}
		IsPaused = true;
		msgService.Call("sound.pause", null, handle);
	}

	public void Resume()
	{
		if (!IsPaused)
		{
			Log.Warning("Sound: was not paused");
			return;
		}
		if (!handleIsValid)
		{
			throw new InvalidOperationException("Sound: can't resume when stopped");
		}
		IsPaused = false;
		msgService.Call("sound.resume", null, handle);
	}

	public void SetVolume(float volume)
	{
		SetVolume(volume, volume);
	}

	public void SetVolume(float volumeLeft, float volumeRight)
	{
		if (!handleIsValid)
		{
			throw new InvalidOperationException("can't set volume when stopped");
		}
		volumeLeft = Mathf.Clamp(volumeLeft, 0f, 1f);
		volumeRight = Mathf.Clamp(volumeRight, 0f, 1f);
		msgService.Call("sound.setVolume", null, handle, volumeLeft, volumeRight);
	}

	internal void HandleStopped()
	{
		handleIsValid = false;
		if (this.StoppedEvent != null)
		{
			this.StoppedEvent(this);
		}
	}

	internal void HandleStarted()
	{
		if (this.StartedEvent != null)
		{
			this.StartedEvent(this);
		}
	}
}
