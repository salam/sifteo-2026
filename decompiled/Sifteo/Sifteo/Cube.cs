using System;
using Sifteo.MathExt;

namespace Sifteo;

public class Cube : IComparable
{
	public enum Side
	{
		TOP,
		LEFT,
		BOTTOM,
		RIGHT,
		NONE
	}

	public const int TILT_X = 0;

	public const int TILT_Y = 1;

	public const int TILT_Z = 2;

	public const int SCREEN_WIDTH = 128;

	public const int SCREEN_HEIGHT = 128;

	public const int SCREEN_MAX_X = 127;

	public const int SCREEN_MAX_Y = 127;

	public const int SCREEN_MIN_X = 0;

	public const int SCREEN_MIN_Y = 0;

	public const int POLYGON_MAX_POINTS = 14;

	public const int ROTATION_MAX = 3;

	public const int SCALE_MAX = 63;

	public const int NEIGHBOR_ID_NONE = 254;

	public const int NUM_SIDES = 4;

	public object userData;

	private IMsgService mMsgService;

	private ImageSet imageSet;

	private static readonly int[] RotationTranslator = new int[4] { 0, 3, 2, 1 };

	internal Cube[] mPhysicalNeighbors = new Cube[4];

	private static readonly Side[,] kOrientToTable = new Side[4, 4]
	{
		{
			Side.BOTTOM,
			Side.LEFT,
			Side.TOP,
			Side.RIGHT
		},
		{
			Side.RIGHT,
			Side.BOTTOM,
			Side.LEFT,
			Side.TOP
		},
		{
			Side.TOP,
			Side.RIGHT,
			Side.BOTTOM,
			Side.LEFT
		},
		{
			Side.LEFT,
			Side.TOP,
			Side.RIGHT,
			Side.BOTTOM
		}
	};

	private bool mButtonState;

	private bool mIsUpright = true;

	private int[] mTiltData = new int[3];

	private int mLastShakeDuration = -1;

	public Neighbors Neighbors { get; private set; }

	public string UniqueId { get; private set; }

	internal int SessionId { get; set; }

	public Side Orientation { get; set; }

	public bool ButtonIsPressed
	{
		get
		{
			return mButtonState;
		}
		internal set
		{
			if (value != mButtonState)
			{
				mButtonState = value;
				if (this.ButtonEvent != null)
				{
					this.ButtonEvent(this, mButtonState);
				}
			}
		}
	}

	public bool IsUpright => mIsUpright;

	public int[] Tilt => mTiltData;

	public bool IsShaking => mLastShakeDuration == 0;

	public event ButtonEventHandler ButtonEvent;

	public event TiltEventHandler TiltEvent;

	public event ShakeStartedHandler ShakeStartedEvent;

	public event ShakeStoppedHandler ShakeStoppedEvent;

	public event FlipEventHandler FlipEvent;

	public event NeighborAddEventHandler NeighborAddEvent;

	public event NeighborRemoveEventHandler NeighborRemoveEvent;

	public void ClearEvents()
	{
		this.ButtonEvent = null;
		this.TiltEvent = null;
		this.ShakeStartedEvent = null;
		this.ShakeStoppedEvent = null;
		this.FlipEvent = null;
		this.NeighborAddEvent = null;
		this.NeighborRemoveEvent = null;
	}

	public int CompareTo(object obj)
	{
		Cube cube = (Cube)obj;
		return SessionId.CompareTo(cube.SessionId);
	}

	internal Cube(IMsgService msgService, Cube[] nbrs, int sessionId, string uniqueId)
	{
		mMsgService = msgService;
		SessionId = sessionId;
		UniqueId = uniqueId;
		Neighbors = new Neighbors(this, nbrs);
		Orientation = Side.TOP;
		imageSet = ((BaseApp.Instance == null) ? new ImageSet() : BaseApp.Instance.Images);
	}

	public void OrientTo(Cube neighbor)
	{
		Side side = Neighbors.CoalescedPhysicalSideOf(neighbor);
		if (side != Side.NONE)
		{
			Side side2 = neighbor.Neighbors.CoalescedPhysicalSideOf(this);
			if (side2 != Side.NONE)
			{
				side2 = (Side)Mathf.Mod(side2 - neighbor.Orientation, 4);
				Orientation = kOrientToTable[(int)side, (int)side2];
			}
		}
	}

	internal void SetTiltData(int x, int y, int z)
	{
		if (x == mTiltData[0] && y == mTiltData[1] && z == mTiltData[2])
		{
			return;
		}
		if (mTiltData[2] != z)
		{
			if (z == 2 && !mIsUpright)
			{
				mIsUpright = true;
				if (this.FlipEvent != null)
				{
					this.FlipEvent(this, mIsUpright);
				}
			}
			else if (z == 0 && mIsUpright)
			{
				mIsUpright = false;
				if (this.FlipEvent != null)
				{
					this.FlipEvent(this, mIsUpright);
				}
			}
		}
		mTiltData[0] = x;
		mTiltData[1] = y;
		mTiltData[2] = z;
		if (this.TiltEvent != null)
		{
			this.TiltEvent(this, mTiltData[0], mTiltData[1], mTiltData[2]);
		}
	}

	internal void SetShakeState(bool startedShaking, int duration)
	{
		if (startedShaking)
		{
			mLastShakeDuration = 0;
			if (this.ShakeStartedEvent != null)
			{
				this.ShakeStartedEvent(this);
			}
		}
		else
		{
			mLastShakeDuration = duration;
			if (this.ShakeStoppedEvent != null)
			{
				this.ShakeStoppedEvent(this, mLastShakeDuration);
			}
		}
	}

	internal Side PhysicalToVirtual(Side side)
	{
		return (Side)Mathf.Mod(side - Orientation, 4);
	}

	internal Side VirtualToPhysical(Side side)
	{
		return (Side)Mathf.Mod((int)side + (int)Orientation, 4);
	}

	internal void ClearPhysicalNeighbors()
	{
		Array.Clear(mPhysicalNeighbors, 0, mPhysicalNeighbors.Length);
	}

	internal void NeighborAdd(Side side, Cube neighbor, Side neighborSide)
	{
		if (mPhysicalNeighbors[(int)side] != neighbor)
		{
			int num = Array.IndexOf(mPhysicalNeighbors, neighbor);
			if (num != -1)
			{
				mPhysicalNeighbors[num] = null;
			}
			mPhysicalNeighbors[(int)side] = neighbor;
		}
	}

	internal Side CoalescedNeighborAdd(Side side, Cube neighbor, Side neighborSide)
	{
		Side side2 = PhysicalToVirtual(side);
		if (this.NeighborAddEvent != null)
		{
			this.NeighborAddEvent(this, side2, neighbor, neighbor.PhysicalToVirtual(neighborSide));
		}
		return PhysicalToVirtual(side);
	}

	internal void NeighborRemove(Side side, Cube neighbor, Side neighborSide)
	{
		if (mPhysicalNeighbors[(int)side] == neighbor)
		{
			mPhysicalNeighbors[(int)side] = null;
		}
	}

	internal Side CoalescedNeighborRemove(Side side, Cube neighbor, Side neighborSide)
	{
		Side side2 = PhysicalToVirtual(side);
		if (this.NeighborRemoveEvent != null)
		{
			this.NeighborRemoveEvent(this, side2, neighbor, neighbor.PhysicalToVirtual(neighborSide));
		}
		return PhysicalToVirtual(side);
	}

	public void FillScreen(Color c)
	{
		mMsgService.Call("cube.fill", null, SessionId, c.Data);
	}

	public void Paint()
	{
		mMsgService.Call("cube.paint", null, SessionId, RotationTranslator[(int)Orientation]);
	}

	public void Image(string name, int x = 0, int y = 0, int sourceX = 0, int sourceY = 0, int w = 128, int h = 128, int scale = 1, int rotation = 0)
	{
		if (!imageSet.Contains(name))
		{
			Log.Warning("image not available: {0}", name);
		}
		else
		{
			if (x > 127 || y > 127)
			{
				return;
			}
			scale = Mathf.Clamp(scale, 0, 63);
			rotation %= 4;
			if (x < 0)
			{
				switch (rotation)
				{
				case 1:
					sourceY -= x;
					h += x;
					break;
				case 2:
					w += x;
					break;
				case 3:
					h += x;
					break;
				default:
					sourceX -= x;
					w += x;
					break;
				}
				x = 0;
			}
			if (y < 0)
			{
				switch (rotation)
				{
				case 1:
					w += y;
					break;
				case 2:
					h += y;
					break;
				case 3:
					sourceX -= y;
					w += y;
					break;
				default:
					sourceY -= y;
					h += y;
					break;
				}
				y = 0;
			}
			switch (rotation)
			{
			case 1:
				if (y + w > 128)
				{
					sourceX += y + w - 128;
				}
				break;
			case 2:
				if (x + w > 128)
				{
					sourceX += x + w - 128;
				}
				if (y + h > 128)
				{
					sourceY += y + h - 128;
				}
				break;
			case 3:
				if (x + h > 128)
				{
					sourceY += x + h - 128;
				}
				break;
			}
			if (w >= 0 && h >= 0)
			{
				if (rotation % 2 == 0)
				{
					ClipToScreen(ref x, ref y, ref w, ref h);
				}
				else
				{
					ClipToScreen(ref x, ref y, ref h, ref w);
				}
				mMsgService.Call("cube.image", null, SessionId, name, x, y, w, h, sourceX, sourceY, scale, rotation);
			}
		}
	}

	internal static void ClipToScreen(ref int x, ref int y, ref int w, ref int h)
	{
		if (x < 0)
		{
			w += x;
			x = 0;
		}
		w = Math.Min(128 - x, w);
		if (y < 0)
		{
			h += y;
			y = 0;
		}
		h = Math.Min(128 - y, h);
		x = Math.Min(x, 127);
		y = Math.Min(y, 127);
	}

	public void FillRect(Color c, int x, int y, int w, int h)
	{
		ClipToScreen(ref x, ref y, ref w, ref h);
		mMsgService.Call("cube.fillRect", null, SessionId, x, y, w, h, c.Data);
	}
}
