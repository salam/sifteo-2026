using System;
using System.IO;

namespace Sifteo;

public class Data
{
	private string filepath;

	public bool IsValid => filepath != null;

	internal Data()
	{
	}

	internal void SetAppID(string id)
	{
		if (id != null && !IsValid)
		{
			string text = Environment.GetEnvironmentVariable("SR_USER_ACCOUNT");
			if (text == null)
			{
				text = "nobody@sifteo.com";
			}
			string folderPath = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
			string path = string.Format("Sifteo/Siftrunner/Users/{0}/Data/{1}.txt", text, id.Replace(".", "_"));
			filepath = Path.Combine(folderPath, path);
			if (!File.Exists(filepath))
			{
				Directory.CreateDirectory(Path.GetDirectoryName(filepath));
			}
		}
	}

	public string Load()
	{
		if (!IsValid)
		{
			throw new InvalidDataException("Data.Load: appID has not been set, Data is not valid!");
		}
		if (!File.Exists(filepath))
		{
			return string.Empty;
		}
		using StreamReader streamReader = new StreamReader(filepath);
		return streamReader.ReadToEnd().TrimEnd(new char[0]);
	}

	public void Store(string data)
	{
		if (!IsValid)
		{
			throw new InvalidDataException("Data.Store: appID has not been set, Data is not valid!");
		}
		using StreamWriter streamWriter = new StreamWriter(filepath);
		streamWriter.WriteLine(data);
	}

	internal void Delete()
	{
		if (!IsValid)
		{
			Log.Warning("Data: not valid, bailing");
		}
		else if (File.Exists(filepath))
		{
			File.Delete(filepath);
		}
	}
}
