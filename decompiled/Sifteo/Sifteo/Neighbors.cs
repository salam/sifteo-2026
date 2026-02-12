using System;
using System.Collections;
using Sifteo.MathExt;

namespace Sifteo;

public class Neighbors : IEnumerable
{
	private Cube[] mCoalescedNeighbors;

	private Cube mParent;

	public Cube this[Cube.Side side]
	{
		get
		{
			if (!SideIsValid(side))
			{
				return null;
			}
			return mCoalescedNeighbors[Mathf.Mod((int)side + (int)mParent.Orientation, 4)];
		}
	}

	public Cube Top => this[Cube.Side.TOP];

	public Cube Left => this[Cube.Side.LEFT];

	public Cube Bottom => this[Cube.Side.BOTTOM];

	public Cube Right => this[Cube.Side.RIGHT];

	public int Count => ((mCoalescedNeighbors[0] != null) ? 1 : 0) + ((mCoalescedNeighbors[1] != null) ? 1 : 0) + ((mCoalescedNeighbors[2] != null) ? 1 : 0) + ((mCoalescedNeighbors[3] != null) ? 1 : 0);

	public bool IsEmpty
	{
		get
		{
			if (mCoalescedNeighbors[0] == null && mCoalescedNeighbors[1] == null && mCoalescedNeighbors[2] == null)
			{
				return mCoalescedNeighbors[3] == null;
			}
			return false;
		}
	}

	internal Neighbors(Cube parent, Cube[] cubes)
	{
		mParent = parent;
		mCoalescedNeighbors = cubes;
	}

	IEnumerator IEnumerable.GetEnumerator()
	{
		return mCoalescedNeighbors.GetEnumerator();
	}

	public static bool SideIsValid(Cube.Side side)
	{
		switch (side)
		{
		case Cube.Side.TOP:
		case Cube.Side.LEFT:
		case Cube.Side.BOTTOM:
		case Cube.Side.RIGHT:
		case Cube.Side.NONE:
			return true;
		default:
			Console.WriteLine("invalid side {0}", side);
			return false;
		}
	}

	public Cube.Side SideOf(Cube neighbor)
	{
		if (neighbor == Top)
		{
			return Cube.Side.TOP;
		}
		if (neighbor == Left)
		{
			return Cube.Side.LEFT;
		}
		if (neighbor == Right)
		{
			return Cube.Side.RIGHT;
		}
		if (neighbor == Bottom)
		{
			return Cube.Side.BOTTOM;
		}
		return Cube.Side.NONE;
	}

	internal Cube.Side CoalescedPhysicalSideOf(Cube neighbor)
	{
		for (int i = 0; i < 4; i++)
		{
			if (mCoalescedNeighbors[i] == neighbor)
			{
				return (Cube.Side)i;
			}
		}
		return Cube.Side.NONE;
	}

	public bool Contains(Cube c)
	{
		if (mCoalescedNeighbors[0] != c && mCoalescedNeighbors[1] != c && mCoalescedNeighbors[2] != c)
		{
			return mCoalescedNeighbors[3] == c;
		}
		return true;
	}

	internal void Clear()
	{
		Array.Clear(mCoalescedNeighbors, 0, mCoalescedNeighbors.Length);
	}

	internal Cube[] BackingArray()
	{
		return mCoalescedNeighbors;
	}
}
